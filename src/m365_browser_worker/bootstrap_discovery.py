"""Fixed, read-only operator bootstrap discovery surface.

OPERATOR-ONLY, loopback-admitted, read-only discovery of the declared
``common.auth`` sign-in selectors against the dedicated live Microsoft 365
professional browser profile.

It reuses ``common_auth_locator_plan`` to load the UNVERIFIED_LIVE structured
plans and the ``locator_runtime`` primitives to count declared candidates only.
It NEVER fills, clicks, types, navigates, evaluates scripts, or returns locator
values, DOM text, URLs, or account data.

Fail-closed invariants (requirement v2):

* admission is a SOCKET-level loopback decision only;
* the fixed key scope is hard-coded per route (email route: two keys; password
  route: two keys). No caller may supply a selector/stage/url/js;
* any query string is rejected and no request body is processed;
* only the sanitized semantic results NO_MATCH / UNIQUE_MATCH / AMBIGUOUS are
  returned. For UNIQUE_MATCH a value-free ``structural_digest`` (sha256 of a
  canonical shape) is returned; its shape semantics are identical to
  ``scripts/collect_live_attestation_observation.py``;
* any precondition failure (no started browser, wrong profile, disapproved
  auth origin, page count != 1, missing/invalid plan, unexpected locator
  error) fails closed with a sanitized 503 and no exception text leaked.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from m365_browser_worker.locator_runtime import build_locator
from m365_browser_worker.operator_signin import common_auth_locator_plan


class DiscoveryResultKind(StrEnum):
    """Sanitized semantic outcome for one fixed selector key."""

    NO_MATCH = "NO_MATCH"
    UNIQUE_MATCH = "UNIQUE_MATCH"
    AMBIGUOUS = "AMBIGUOUS"


# Fixed hard-coded discovery scope. No caller may supply these values.
EMAIL_DISCOVERY_KEYS = ("auth.login_email_input", "auth.login_next_button")
PASSWORD_DISCOVERY_KEYS = ("auth.login_password_input", "auth.login_signin_button")

# Operation names used only for sanitized fail-closed detail/observability.
DISCOVER_EMAIL_OPERATION = "auth_bootstrap_discover_email"
DISCOVER_PASSWORD_OPERATION = "auth_bootstrap_discover_password"  # noqa: S105


class DiscoveryError(Exception):
    """Fail-closed discovery precondition/error. No values are leaked.

    Carries only a sanitized ``reason`` category. It must never include DOM
    text, selector strings, candidate values, or raw exception text.
    """

    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(f"bootstrap discovery failed: {reason}")


# ---------------------------------------------------------------------------
# Canonical structural digest (compatible with
# scripts/collect_live_attestation_observation.py).
#
# Reimplemented here so the worker runtime never imports the operator script as
# a runtime API and packaging is not widened. The shape and hashing are identical
# to the script's ``_selector_structural_shape`` / ``_structural_digest``.
# ---------------------------------------------------------------------------


def _structural_digest(shape: dict[str, Any]) -> str:
    """Hash a sanitized value-free structural shape deterministically.

    Mirrors ``scripts/collect_live_attestation_observation.py:_structural_digest``
    exactly: canonical JSON (sort_keys, no whitespace) of the shape, then a
    ``sha256:``-prefixed hex digest.
    """
    canonical = json.dumps(shape, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return f"sha256:{hashlib.sha256(canonical.encode('utf-8')).hexdigest()}"


def _selector_structural_shape(
    selector_key: str,
    metadata: dict[str, Any],
    match_index: int,
    match_count: int,
) -> dict[str, Any]:
    """Build a closed, value-free structural shape for one selector match.

    Mirrors ``scripts/collect_live_attestation_observation.py:
    _selector_structural_shape`` exactly: the locator *strategy* (derived from
    the plan's primary candidate) is preserved as a structural signal, while the
    locator *value* and any accessible name text are dropped so no tenant content
    leaves the discovery boundary.
    """
    from m365_mcp.locators import locator_plan_from_metadata

    plan = locator_plan_from_metadata(selector_key, metadata)
    strategy = plan.primary.strategy.value if plan is not None else "undeclared"
    return {
        "selector_key": selector_key,
        "strategy": strategy,
        "match_index": match_index,
        "match_count": match_count,
    }


@dataclass(frozen=True)
class KeyDiscovery:
    """Sanitized per-key discovery outcome. No values or DOM text."""

    selector_key: str
    result: DiscoveryResultKind
    structural_digest: str | None

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "selector_key": self.selector_key,
            "result": self.result.value,
        }
        if self.structural_digest is not None:
            # Only present for UNIQUE_MATCH, and only a value-free digest.
            payload["structural_digest"] = self.structural_digest
        return payload


async def discover_key(page: Any, selector_key: str) -> KeyDiscovery:
    """Resolve/count declared candidates only for one fixed selector key.

    Reuses ``common_auth_locator_plan`` (UNVERIFIED_LIVE plans are permitted,
    attestation is NOT required) and the ``locator_runtime.build_locator``
    primitive to count each declared candidate. It performs NO wait, NO visible
    assertion, NO fill, NO click, and NO navigation. The returned shape is a
    sanitized semantic result only.

    Raises ``DiscoveryError`` (fail closed) when the plan is missing/invalid or a
    locator count cannot be determined. ``LocatorRuntimeError`` is never raised
    here because ambiguity is mapped to the sanitized AMBIGUOUS result rather than
    an exception.
    """
    try:
        plan = common_auth_locator_plan(selector_key)
    except ValueError as exc:
        raise DiscoveryError("invalid locator plan") from exc
    if plan is None:
        raise DiscoveryError("missing locator plan")

    # Resolve/count the declared PRIMARY candidate only (identical to the
    # operator script's live probe, which builds the locator from the plan's
    # primary candidate and counts matches). This yields a single semantic
    # count: 0 = NO_MATCH, 1 = UNIQUE_MATCH, >1 = AMBIGUOUS. No DOM text, no
    # values, no interaction, no wait.
    primary = plan.primary
    locator = build_locator(page, primary)
    try:
        count = int(await locator.count())
    except Exception as exc:
        raise DiscoveryError("locator count could not be determined") from exc

    if count > 1:
        return KeyDiscovery(selector_key, DiscoveryResultKind.AMBIGUOUS, None)
    if count == 1:
        # UNIQUE_MATCH: digest uses the canonical script-compatible shape with
        # match_index=0 and match_count=1 (the only determined values).
        metadata = {"locators": [candidate.to_dict() for candidate in plan.ordered_candidates()]}
        shape = _selector_structural_shape(selector_key, metadata, match_index=0, match_count=1)
        return KeyDiscovery(
            selector_key, DiscoveryResultKind.UNIQUE_MATCH, _structural_digest(shape)
        )
    return KeyDiscovery(selector_key, DiscoveryResultKind.NO_MATCH, None)
