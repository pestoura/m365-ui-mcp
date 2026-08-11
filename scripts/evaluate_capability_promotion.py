#!/usr/bin/env python3
"""Evaluate sanitized evidence for a repository-side capability promotion decision."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from m365_mcp.capability_promotion import (
    LiveSupportState,
    PromotionPolicy,
    evaluate_promotion,
    evidence_from_dict,
)
from m365_mcp.capability_registry import default_capability_registry


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Evaluate sanitized live-probe evidence. This command never drives a browser, "
            "changes tenant state, or promotes mock/synthetic evidence."
        )
    )
    parser.add_argument("evidence", type=Path)
    parser.add_argument("--environment", required=True)
    parser.add_argument("--contract-set-digest", required=True)
    parser.add_argument("--required-gate", action="append", default=[])
    parser.add_argument("--max-age-seconds", type=int, default=3600)
    parser.add_argument(
        "--previous-state",
        choices=[state.value for state in LiveSupportState],
        default=LiveSupportState.LIVE_UNOBSERVED.value,
    )
    parser.add_argument(
        "--dependencies-accepted",
        action="store_true",
        help="set only when the ordered live acceptance dependencies are accepted",
    )
    parser.add_argument(
        "--now",
        default=None,
        help="optional ISO-8601 evaluation time for deterministic tests/audits",
    )
    return parser


def _read_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("promotion evidence document must be a JSON object")
    return data


def _parse_now(raw: str | None) -> datetime:
    if raw is None:
        return datetime.now(UTC)
    value = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("--now must be timezone-aware")
    return value.astimezone(UTC)


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    evidence = evidence_from_dict(_read_json(args.evidence))
    policy = PromotionPolicy(
        environment_id=args.environment,
        current_contract_set_digest=args.contract_set_digest,
        required_gate_ids=tuple(args.required_gate),
        max_age=timedelta(seconds=args.max_age_seconds),
        dependencies_accepted=args.dependencies_accepted,
    )
    decision = evaluate_promotion(
        default_capability_registry(),
        evidence,
        policy,
        previous_state=LiveSupportState(args.previous_state),
        now=_parse_now(args.now),
    )
    print(json.dumps(decision.to_dict(), indent=2, sort_keys=True))
    return 0 if decision.promotable else 3


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"promotion evaluation error: {exc}", file=sys.stderr)
        raise SystemExit(4) from exc
