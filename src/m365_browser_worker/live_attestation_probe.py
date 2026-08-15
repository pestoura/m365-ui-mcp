"""Live-worker UI attestation probe (operator-only, local-only, fail-closed).

UI-AUTH-001. Reuses the ALREADY-RUNNING Playwright ``browser._context`` (the
dedicated persistent professional profile) to collect sanitized UI-attestation
evidence for the ``planner.plan-surface`` and ``planner.task-surface``
UIContract fragments. It NEVER opens a second persistent Chromium context and
NEVER destroys the already-authenticated Microsoft session.

It is the sanitized sibling of ``collect_observation`` (AUTH-105) and
``bootstrap_discovery`` (v2): same loopback-only, read-only, fixed-scope,
value-free evidence contract, scoped to the Planner surface fragments instead of
the four ``common.auth`` progression selectors.

Hard invariants (no weakening of the fail-closed model):

* Output contains ONLY fragment/selector IDs known to the contract set, a fresh
  contract-set digest, match counts, and the closed results
  ``UNIQUE_MATCH`` / ``NO_MATCH`` / ``AMBIGUOUS`` / ``NO_LOCATOR``. No raw DOM,
  page text, URLs, cookies, tokens, UPN, tenant IDs, or account identity leaves
  this module.
* It reuses the live ``browser._context`` only — read-only, no wait, no
  interaction, no navigation, no ``page.evaluate``.
* It NEVER invents selectors or locators (CORE-019): a fragment selector that
  carries no declared ``locators`` plan is reported as ``NO_LOCATOR`` (honest
  blocker), never fabricated.
* It binds to the CURRENT ``contract_set_digest`` and uses the canonical
  value-free structural-digest shape, identical to
  ``m365_mcp.attestation_collection``.
* It NEVER marks a contract fragment ATTESTED. Promotion stays PR/evidence based.
* It NEVER writes, edits or self-promotes source contract JSON.
* ``live_probe`` is injected by the caller and MUST return only a sanitized match
  count (0 = NO_MATCH, 1 = UNIQUE_MATCH, >1 = AMBIGUOUS); it MUST NOT return raw
  content.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from m365_mcp.locators import locator_plan_from_metadata
from m365_mcp.ui_contract_store import load_ui_contract_set

# Fixed hard-coded observation scope. No caller may supply these values.
PLANNER_SURFACE_FRAGMENT_IDS = ("planner.plan-surface", "planner.task-surface")

# Operation name used only for sanitized fail-closed detail/observability. It is
# free of the tokens ``goto``/``navigate`` (auth_bootstrap.py greps for those).
PROBE_PLANNER_SURFACE_OPERATION = "auth_bootstrap_probe_planner_surface"


class LiveProbeError(Exception):
    """Fail-closed live-surface precondition/error. No values are leaked.

    Carries only a sanitized ``reason`` category. It must never include DOM
    text, selector strings, candidate values, or raw exception text.
    """

    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(f"live surface probe failed: {reason}")


# ---------------------------------------------------------------------------
# Canonical structural digest (value-free, identical to
# m365_mcp.attestation_collection + bootstrap_discovery).
# ---------------------------------------------------------------------------


def _structural_digest(shape: dict[str, Any]) -> str:
    """Hash a sanitized value-free structural shape deterministically."""
    canonical = json.dumps(shape, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return f"sha256:{hashlib.sha256(canonical.encode('utf-8')).hexdigest()}"


def _selector_structural_shape(
    selector_key: str,
    metadata: dict[str, Any],
    match_index: int,
    match_count: int,
) -> dict[str, Any]:
    """Build a closed, value-free structural shape for one selector match."""
    plan = locator_plan_from_metadata(selector_key, metadata)
    strategy = plan.primary.strategy.value if plan is not None else "undeclared"
    return {
        "selector_key": selector_key,
        "strategy": strategy,
        "match_index": match_index,
        "match_count": match_count,
    }


def _count_for_selector(
    selector_key: str,
    metadata: dict[str, Any],
    live_probe: Any,
) -> dict[str, Any]:
    """Resolve/count one declared selector against the live page, sanitized.

    Returns a closed dict with only the selector_key and a result. A missing
    locators plan is reported as ``NO_LOCATOR`` (honest, no fabrication). A
    declared plan is counted via the injected ``live_probe`` (count only).
    """
    plan = locator_plan_from_metadata(selector_key, metadata)
    if plan is None:
        # No declared locators plan: CORE-019 forbids inventing a selector.
        # Report the honest blocker rather than fabricating evidence.
        return {"selector_key": selector_key, "result": "NO_LOCATOR"}

    try:
        count = int(live_probe(selector_key, metadata, plan))
    except Exception as exc:  # noqa: BLE001 - sanitized fail-closed
        raise LiveProbeError("locator count could not be determined") from exc

    if count > 1:
        return {"selector_key": selector_key, "result": "AMBIGUOUS"}
    if count == 1:
        shape = _selector_structural_shape(
            selector_key, metadata, match_index=0, match_count=1
        )
        return {
            "selector_key": selector_key,
            "result": "UNIQUE_MATCH",
            "structural_digest": _structural_digest(shape),
        }
    return {"selector_key": selector_key, "result": "NO_MATCH"}


async def probe_live_surface_fragment(
    browser: Any,
    *,
    fragment_id: str,
    live_probe: Any | None = None,
) -> dict[str, Any]:
    """Collect sanitized UI-attestation evidence for one Planner surface fragment.

    Reuses the live ``browser._context`` (read-only). The injected ``live_probe``
    counts declared candidates against the single live page only. It performs no
    wait, no visible assertion, no fill, no click, no navigation, no
    ``page.evaluate``. Only a sanitized match count (0/1/>1) and a value-free
    structural digest leave this function.

    Raises ``LiveProbeError`` (fail closed) when the fragment is unknown, the
    running context is unusable, the positive Planner Web surface is absent, the
    page set is ambiguous, or any selector cannot be deterministically counted.
    It NEVER fabricates a match: an unlocatable selector yields an honest
    ``NO_LOCATOR`` result that the evaluator will reject, exactly as designed.
    """
    if fragment_id not in PLANNER_SURFACE_FRAGMENT_IDS:
        raise LiveProbeError("unsupported observation fragment")

    if browser is None or not getattr(browser, "started", False):
        raise LiveProbeError("live probe requires a started live browser")
    if not browser.is_dedicated_persistent_profile():
        raise LiveProbeError("live probe requires the dedicated persistent profile")
    # Positive surface proof: the dedicated profile must sit on the fixed
    # Planner Web surface (the post-MFA landing surface). Absence is NOT
    # treated as authenticated — fail closed.
    if not browser.planner_web_surface_present():
        raise LiveProbeError("live probe requires the Planner Web surface")

    context = getattr(browser, "_context", None)
    if context is None:
        raise LiveProbeError("live probe requires an owned browser context")
    pages = list(getattr(context, "pages", []) or [])
    if len(pages) != 1:
        # Exactly one open page is required: an ambiguous multi-page topology
        # must never be accepted as the authenticated surface.
        raise LiveProbeError("live probe requires exactly one open page")

    contract_set = load_ui_contract_set()
    fragment = next(
        (item for item in contract_set.fragments if item.fragment_id == fragment_id),
        None,
    )
    if fragment is None:
        raise LiveProbeError("fragment not present in contract set")
    if fragment.drifted:
        raise LiveProbeError("fragment is drifted")

    page = pages[0]

    async def _default_live_probe(
        selector_key: str, metadata: dict[str, Any], plan: Any
    ) -> int:
        # Resolve/count the declared PRIMARY candidate only. Mirrors
        # bootstrap_discovery.discover_key / collect_observation.live_probe.
        from m365_browser_worker.locator_runtime import build_locator

        locator = build_locator(page, plan.primary)
        try:
            return int(await locator.count())
        except Exception as exc:  # noqa: BLE001 - sanitized fail-closed
            raise LiveProbeError("locator count could not be determined") from exc

    probe = live_probe or _default_live_probe

    selector_results: list[dict[str, Any]] = []
    for selector_key, metadata in fragment.selectors.items():
        result = _count_for_selector(selector_key, metadata, probe)
        selector_results.append(result)

    all_unique_match = all(r["result"] == "UNIQUE_MATCH" for r in selector_results)

    return {
        "fragment_id": fragment.fragment_id,
        "contract_set_digest": contract_set.digest(),
        "surface_present": True,
        "page_count": len(pages),
        "selectors": selector_results,
        "all_unique_match": all_unique_match,
    }


async def probe_all_live_surface_fragments(browser: Any) -> list[dict[str, Any]]:
    """Probe every allowlisted Planner surface fragment, fail-closed per fragment.

    Returns one sanitized result dict per fragment. A ``LiveProbeError`` on any
    fragment is converted to a sanitized error payload (no exception text leaks);
    the caller's route maps these to a 503 envelope.
    """
    results: list[dict[str, Any]] = []
    for fragment_id in PLANNER_SURFACE_FRAGMENT_IDS:
        try:
            results.append(
                await probe_live_surface_fragment(browser, fragment_id=fragment_id)
            )
        except LiveProbeError as exc:
            results.append(
                {
                    "fragment_id": fragment_id,
                    "error": exc.reason,
                }
            )
    return results


__all__ = [
    "PLANNER_SURFACE_FRAGMENT_IDS",
    "PROBE_PLANNER_SURFACE_OPERATION",
    "LiveProbeError",
    "probe_all_live_surface_fragments",
    "probe_live_surface_fragment",
]
