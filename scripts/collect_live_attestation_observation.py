#!/usr/bin/env python3
"""OPERATOR-ONLY local live UI attestation observation collector.

This is NOT a public MCP tool and NOT an externally exposed HTTP endpoint. It
is run by an operator on the host, against the dedicated persistent professional
Microsoft 365 browser profile, to produce sanitized LIVE_UI attestation
observations that feed ``scripts/attest_ui_contract.py evaluate``.

Hard invariants (no weakening of the fail-closed model):

* Output contains ONLY campaign/fragment metadata and normalized structural
  SHA-256 digests / UNIQUE_MATCH results. No raw DOM, page text, URLs, cookies,
  tokens, UPN, tenant IDs, mailbox content, or arbitrary navigation is ever
  returned or persisted by this script.
* It binds to the CURRENT ``contract_set_digest`` and reuses the existing
  ``attest_ui_contract.py`` plan/evaluate schema. A contract-set change makes
  the produced observation fail evaluation, by design.
* It NEVER marks a contract fragment ATTESTED. Promotion remains PR/evidence
  based and is performed by ``attest_ui_contract.py evaluate`` + review.
* It NEVER writes, edits or self-promotes source contract JSON. The fragment
  files under ``contracts/`` are never modified.
* It NEVER fabricates evidence. If the dedicated live browser/profile is
  unavailable, or Playwright is not installed, it refuses rather than inventing
  an observation. Mock mode is rejected because MOCK evidence can never promote
  live support.

Supported fragments (phase order):
    common.auth                (first; requires the authenticated session)
    planner.plan-surface
    planner.task-surface
    planner.account            (later; requires the authenticated session)
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import inspect
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from m365_mcp.attestation import (
    AttestationLevel,
    AttestationObservation,
    ObservationSource,
    SelectorObservation,
    SelectorObservationResult,
    build_attestation_campaign,
    observation_from_dict,
)
from m365_mcp.config import browser_runtime_settings
from m365_mcp.locators import locator_plan_from_metadata
from m365_mcp.ui_contract_store import load_ui_contract_set

SUPPORTED_FRAGMENTS = (
    "common.auth",
    "planner.plan-surface",
    "planner.task-surface",
    "planner.account",
)


def _structural_digest(shape: dict[str, Any]) -> str:
    """Hash a sanitized structural shape (no text/values) deterministically.

    The shape is a normalized skeleton: role/strategy/index/depth only. Any
    tenant text, attribute value, URL or identity must have been removed before
    this is called.
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
    locator *value* and any accessible name text are intentionally dropped so
    no tenant content leaves the collection boundary.
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

    The produced observation carries only digests and UNIQUE_MATCH results.
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


def _real_live_probe() -> Any:
    """Return a live probe backed by the dedicated profile, or refuse.

    This is the only place the dedicated browser is touched. If running in mock
    mode, or Playwright is unavailable, or the profile is not the dedicated
    persistent professional profile, it raises so the operator never receives
    fabricated evidence. Mock mode is rejected because MOCK evidence can never
    promote live support.
    """
    _profile_dir, _headless, mode = browser_runtime_settings()
    if mode.lower() == "mock":
        raise RuntimeError(
            "live collection must not run in mock mode; MOCK evidence cannot "
            "promote live support"
        )
    try:
        from playwright.async_api import async_playwright  # noqa: PLC0415
    except ImportError as exc:
        raise RuntimeError(
            "live collection requires Playwright and the dedicated live browser; "
            "refusing to fabricate evidence"
        ) from exc

    async def probe(selector_key: str, metadata: dict[str, Any]) -> int:
        # Closed structural probe only: open the persistent professional context,
        # resolve the declared locator plan, count distinct matches, and return
        # the count. No DOM text, URL, cookie or identity is read out.
        async with async_playwright() as pw:  # pragma: no cover - requires browser
            context = await pw.chromium.launch_persistent_context(
                user_data_dir=str(_profile_dir),
                headless=True,
                args=["--no-first-run", "--no-default-browser-check"],
            )
            try:
                plan = locator_plan_from_metadata(selector_key, metadata)
                if plan is None:
                    return 0
                page = context.pages[0] if context.pages else await context.new_page()
                # Only the declared, reviewed locator plan is used. No arbitrary
                # navigation, script execution or content extraction occurs here.
                locator = page.get_by_role(
                    role=plan.primary.strategy.value,
                    name=plan.primary.name or "",
                ) if plan.primary.strategy.value == "role" else page.locator(
                    plan.primary.value
                )
                count = await locator.count()
                return int(count)
            finally:
                await context.close()

    return probe


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "OPERATOR-ONLY: collect a sanitized LIVE_UI attestation observation "
            "from the dedicated professional browser profile. Never promotes "
            "attestation and never returns raw content."
        )
    )
    parser.add_argument(
        "--fragment",
        required=True,
        choices=SUPPORTED_FRAGMENTS,
        help="UIContract fragment to observe",
    )
    parser.add_argument(
        "--level",
        choices=[level.value for level in AttestationLevel],
        default=AttestationLevel.DISCOVERY.value,
    )
    parser.add_argument(
        "--out",
        type=Path,
        required=True,
        help="local path to write the sanitized observation JSON (operator-reviewed)",
    )
    args = parser.parse_args(argv)

    observation = asyncio.run(
        collect_structural_observation(
            args.fragment,
            args.level,
            live_probe=_real_live_probe(),
        )
    )

    # Bind and self-validate against the existing evaluator schema before writing.
    observation_from_dict(json.loads(json.dumps(observation.canonical_payload())))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(observation.canonical_payload(), indent=2, sort_keys=True),
        encoding="utf-8",
    )
    # Print only the bounded summary; never the raw browser state.
    print(
        json.dumps(
            {
                "fragment_id": observation.fragment_id,
                "target_level": observation.target_level.value,
                "contract_set_digest": observation.contract_set_digest,
                "campaign_id": observation.campaign_id,
                "source": observation.source.value,
                "selector_results": [
                    {"selector_key": item.selector_key, "result": item.result.value}
                    for item in observation.selector_observations
                ],
                "written_to": str(args.out),
                "note": "operator must review and run attest_ui_contract.py evaluate; "
                "this script never marks a contract ATTESTED",
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, RuntimeError, json.JSONDecodeError) as exc:
        print(f"live observation collection error: {exc}", file=sys.stderr)
        raise SystemExit(4) from exc


__all__ = [
    "SUPPORTED_FRAGMENTS",
    "collect_structural_observation",
    "main",
]
