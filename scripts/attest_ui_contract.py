#!/usr/bin/env python3
"""Plan or evaluate a deterministic, sanitized UI attestation campaign."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from m365_mcp.attestation import (
    AttestationDecisionState,
    AttestationLevel,
    build_attestation_campaign,
    evaluate_attestation_observation,
    observation_from_dict,
)
from m365_mcp.capability_evidence import CapabilityEvidenceStore
from m365_mcp.ui_contract_store import load_ui_contract_set


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Plan/evaluate sanitized UI attestation. This tool never drives a browser "
            "and never collects tenant content."
        )
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    plan = subparsers.add_parser("plan", help="emit deterministic campaign metadata")
    plan.add_argument(
        "--level",
        choices=[level.value for level in AttestationLevel],
        default=AttestationLevel.DISCOVERY.value,
    )
    plan.add_argument(
        "--fragment",
        action="append",
        default=None,
        help="fragment id to include; repeatable; defaults to all fragments",
    )

    evaluate = subparsers.add_parser(
        "evaluate", help="evaluate one sanitized observation JSON document"
    )
    evaluate.add_argument("observation", type=Path)
    evaluate.add_argument(
        "--state",
        type=Path,
        default=None,
        help="optional absolute SQLite path for CORE-018 evidence persistence",
    )
    return parser


def _read_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("attestation observation document must be a JSON object")
    return data


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    contract_set = load_ui_contract_set()

    if args.command == "plan":
        fragments = tuple(args.fragment) if args.fragment else None
        campaign = build_attestation_campaign(
            contract_set,
            AttestationLevel(args.level),
            fragment_ids=fragments,
        )
        print(json.dumps(campaign.to_dict(), indent=2, sort_keys=True))
        return 0

    observation = observation_from_dict(_read_json(args.observation))
    decision = evaluate_attestation_observation(contract_set, observation)
    if args.state is not None:
        store = CapabilityEvidenceStore(args.state)
        store.append(decision.evidence_record, contract_set=contract_set)
    print(json.dumps(decision.to_dict(), indent=2, sort_keys=True))

    if decision.state is AttestationDecisionState.PASSED:
        return 0
    if decision.state is AttestationDecisionState.REVIEW_REQUIRED:
        return 2
    return 3


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"attestation error: {exc}", file=sys.stderr)
        raise SystemExit(4) from exc
