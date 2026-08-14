"""Operator-only read-only live attestation observation collector.

OPERATOR-ONLY, socket-loopback admitted, read-only observation of the
EXACT four declared ``common.auth`` sign-in selectors against the
ALREADY-RUNNING dedicated live Microsoft 365 professional browser context.

This is the minimal primitive that closes the evidence gap documented in
``references/common_auth_four_selector_gate.md``: there was no way to produce a
complete ``AttestationObservation`` (``source=LIVE_UI``, current
``contract_set_digest``/campaign binding, selector order exactly matching the
fragment, per-selector result + structural_digest only) from the live context
without relaunching Playwright. The ``discover-*`` routes emit only per-stage
fragments, which the evaluator rejects with ``SELECTOR_SET_OR_ORDER_MISMATCH``.

Hard invariants (requirement AUTH-105):

* admission is a SOCKET-level loopback decision only (``is_loopback_peer``);
* the fixed key scope is exactly the four ``common.auth`` progression selectors in
  fragment order: ``auth.login_email_input`` -> ``auth.login_next_button`` ->
  ``auth.login_password_input`` -> ``auth.login_signin_button``. No caller may
  supply a selector/stage/url/js;
* any query string is rejected and no request body is processed;
* it reuses ``collect_structural_observation`` exactly so the produced
  ``AttestationObservation`` is byte-for-byte evaluator-compatible with
  ``scripts/collect_live_attestation_observation.py`` and ``attest_ui_contract.py
  evaluate``;
* it NEVER fills, clicks, types, navigates, evaluates scripts, or returns locator
  values, DOM text, URLs, cookies, tokens, UPN, tenant ids, or account data;
* it never weakens the fail-closed evaluator or the attestation gate: the produced
  observation carries ``source=LIVE_UI`` and ``target_level=DISCOVERY``, so
  ``evaluate_attestation_observation`` can only ever return ``REVIEW_REQUIRED``
  (``DISCOVERY_EVIDENCE_RECORDED_CONTRACT_REVIEW_REQUIRED`` / ``..._REVIEW_REQUIRED``)
  — promotion stays PR/evidence based;
* it NEVER marks a contract fragment ATTESTED. Source of truth remains in the
  reviewed fragment files under ``contracts/ui_fragments/``.

The injected live probe reads the running ``browser._context`` (owned by this
process) and counts declared candidates only via ``locator_runtime.build_locator``.
It performs NO wait, NO visible assertion, NO fill, NO click, NO navigation, NO
``page.evaluate``. Only a sanitized match count (0/1/>1) leaves the probe.
"""

from __future__ import annotations

from typing import Any

from m365_browser_worker.bootstrap_discovery import DiscoveryError
from m365_browser_worker.locator_runtime import build_locator
from m365_browser_worker.operator_signin import (
    EMAIL_SELECTOR_NAME,
    NEXT_SELECTOR_NAME,
    PASSWORD_SELECTOR_NAME,
    SIGNIN_SELECTOR_NAME,
)
from m365_mcp.attestation import (
    AttestationLevel,
    AttestationObservation,
    ObservationSource,
)
from m365_mcp.attestation_collection import collect_structural_observation
from m365_mcp.locators import locator_plan_from_metadata

# Fixed, hard-coded observation scope. Exactly the four common.auth progression
# selectors, in fragment order. No caller may supply these values.
COLLECT_OBSERVATION_KEYS = (
    EMAIL_SELECTOR_NAME,
    NEXT_SELECTOR_NAME,
    PASSWORD_SELECTOR_NAME,
    SIGNIN_SELECTOR_NAME,
)

# Operation name used only for sanitized fail-closed detail/observability. It is
# free of the tokens ``goto``/``navigate`` (auth_bootstrap.py greps for those).
COLLECT_OBSERVATION_OPERATION = "auth_bootstrap_collect_observation"


async def collect_running_observation(
    browser: Any,
    *,
    fragment_id: str = "common.auth",
    level: AttestationLevel | str = AttestationLevel.DISCOVERY,
) -> AttestationObservation:
    """Build a complete LIVE_UI AttestationObservation from the running context.

    Reuses ``collect_structural_observation`` so the produced bundle is identical
    in shape and binding to the operator host script. The injected ``live_probe``
    counts declared candidates against ``browser._context`` only — read-only,
    no wait, no interaction.

    Raises ``DiscoveryError`` (fail closed) when the running context is unusable
    or any selector cannot be deterministically counted. It NEVER fabricates a
    match: a missing/ambiguous running surface yields honest NO_MATCH/AMBIGUOUS
    results that the evaluator will reject, exactly as designed.
    """
    if browser is None or not getattr(browser, "started", False):
        raise DiscoveryError("live observation requires a started live browser")
    context = getattr(browser, "_context", None)
    if context is None:
        raise DiscoveryError("live observation requires an owned browser context")

    async def live_probe(selector_key: str, metadata: dict[str, Any]) -> int:
        # Resolve/count the declared PRIMARY candidate only. Mirrors
        # bootstrap_discovery.discover_key: a single sanitized match count,
        # no DOM text, no values, no interaction.
        plan = locator_plan_from_metadata(selector_key, metadata)
        if plan is None:
            return 0
        page = context.pages[0] if context.pages else await context.new_page()
        locator = build_locator(page, plan.primary)
        try:
            return int(await locator.count())
        except Exception as exc:  # noqa: BLE001 - sanitized fail-closed
            raise DiscoveryError("locator count could not be determined") from exc


    # collect_structural_observation awaits coroutine probes automatically
    # (inspect.iscoroutine), so passing the async live_probe is correct.
    observation = await collect_structural_observation(
        fragment_id,
        level,
        live_probe=live_probe,
    )
    # Defensive: this primitive only ever emits LIVE_UI evidence. The script
    # default is already LIVE_UI, but pin it so a caller cannot weaken source.
    if observation.source is not ObservationSource.LIVE_UI:
        raise DiscoveryError("live observation produced non-LIVE_UI evidence")
    return observation


def collect_keys() -> tuple[str, ...]:
    """Return the fixed observation key scope (fragment order)."""
    return COLLECT_OBSERVATION_KEYS


__all__ = [
    "COLLECT_OBSERVATION_KEYS",
    "COLLECT_OBSERVATION_OPERATION",
    "collect_keys",
    "collect_running_observation",
]
