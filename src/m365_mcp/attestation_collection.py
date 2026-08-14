"""Shared live attestation observation builder (importable by worker runtime).

This module holds the minimal, browser-free structural observation builder that
was previously only reachable through ``scripts/collect_live_attestation_observation.py``.
Moving it into the package (1) lets the browser-worker runtime build a complete,
evaluator-compatible ``AttestationObservation`` against the ALREADY-RUNNING context
without copying the script into the worker image, and (2) guarantees the operator
host script and the runtime collector produce byte-identical ``canonical_payload``
shapes, digests and campaign bindings.

Hard invariants (no weakening of the fail-closed model):

* Output contains ONLY campaign/fragment metadata and normalized structural
  SHA-256 digests / UNIQUE_MATCH results. No raw DOM, page text, URLs, cookies,
  tokens, UPN, tenant IDs, mailbox content, or arbitrary navigation is ever
  returned or persisted by this builder.
* It binds to the CURRENT ``contract_set_digest`` and reuses the existing
  ``attest_ui_contract.py`` plan/evaluate schema. A contract-set change makes the
  produced observation fail evaluation, by design.
* It NEVER marks a contract fragment ATTESTED. Promotion remains PR/evidence
  based and is performed by ``attest_ui_contract.py evaluate`` + review.
* It NEVER writes, edits or self-promotes source contract JSON.
* ``live_probe`` is injected by the caller and MUST return only a sanitized match
  count (0 = NO_MATCH, 1 = UNIQUE_MATCH, >1 = AMBIGUOUS); it MUST NOT return raw
  content. The builder performs no browser interaction itself.
"""

from __future__ import annotations

import hashlib
import inspect
import json
from datetime import UTC, datetime
from typing import Any

from .attestation import (
    AttestationLevel,
    AttestationObservation,
    ObservationSource,
    SelectorObservation,
    SelectorObservationResult,
    build_attestation_campaign,
)
from .locators import locator_plan_from_metadata
from .ui_contract_store import load_ui_contract_set


def _structural_digest(shape: dict[str, Any]) -> str:
    """Hash a sanitized structural shape (no text/values) deterministically.

    The shape is a normalized skeleton: selector_key/strategy/index/count only.
    Any tenant text, attribute value, URL or identity must have been removed
    before this is called. Identical to the operator script's helper so digests
    match across runtime and host-collected evidence.
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

    Locator strategy availability is preserved as a structural signal; the
    locator *value* and any accessible name text are intentionally dropped so no
    tenant content leaves the collection boundary.
    """
    plan = locator_plan_from_metadata(selector_key, metadata)
    strategy = plan.primary.strategy.value if plan is not None else "undeclared"
    return {
        "selector_key": selector_key,
        "strategy": strategy,
        "match_index": match_index,
        "match_count": match_count,
    }


async def collect_structural_observation(
    fragment_id: str,
    level: AttestationLevel | str,
    *,
    live_probe: Any,
) -> AttestationObservation:
    """Build a sanitized LIVE_UI observation bound to the current contract set.

    ``live_probe`` is an injectable callable:
        live_probe(selector_key, metadata) -> int
    returning the number of structurally distinct matches found in the dedicated
    live browser context (0 = NO_MATCH, 1 = UNIQUE_MATCH, >1 = AMBIGUOUS). It
    MUST NOT return raw content; only a count derived from a sanitized probe.

    The produced observation carries only digests and UNIQUE_MATCH results. The
    caller is responsible for refusing fabricated evidence (e.g. when Playwright
    or the dedicated persistent professional profile is absent); this builder only
    maps counts to results.
    """
    contract_set = load_ui_contract_set()
    campaign = build_attestation_campaign(
        contract_set,
        AttestationLevel(level),
        fragment_ids=(fragment_id,),
    )
    fragment = next(
        item for item in contract_set.fragments if item.fragment_id == fragment_id
    )

    selector_observations: list[SelectorObservation] = []
    for step in campaign.steps:
        metadata = fragment.selectors[step.selector_key]
        # The injected live_probe may be a sync test double or the async locator
        # probe. Await only when required by the existing interface; never weaken
        # the fail-closed structural-only contract (count, no content).
        result = live_probe(step.selector_key, metadata)
        if inspect.iscoroutine(result):
            result = await result
        match_count = int(result)
        if match_count == 1:
            result = SelectorObservationResult.UNIQUE_MATCH
            shape = _selector_structural_shape(
                step.selector_key, metadata, match_index=0, match_count=1
            )
            selector_observations.append(
                SelectorObservation(
                    selector_key=step.selector_key,
                    result=result,
                    structural_digest=_structural_digest(shape),
                )
            )
        elif match_count == 0:
            selector_observations.append(
                SelectorObservation(
                    selector_key=step.selector_key,
                    result=SelectorObservationResult.NO_MATCH,
                )
            )
        else:
            selector_observations.append(
                SelectorObservation(
                    selector_key=step.selector_key,
                    result=SelectorObservationResult.AMBIGUOUS,
                )
            )

    return AttestationObservation(
        campaign_id=campaign.campaign_id,
        contract_set_digest=campaign.contract_set_digest,
        fragment_id=fragment.fragment_id,
        fragment_version=fragment.fragment_version,
        target_level=AttestationLevel(level),
        source=ObservationSource.LIVE_UI,
        observed_at=datetime.now(UTC),
        selector_observations=tuple(selector_observations),
    )


__all__ = [
    "collect_structural_observation",
    "_structural_digest",
    "_selector_structural_shape",
]
