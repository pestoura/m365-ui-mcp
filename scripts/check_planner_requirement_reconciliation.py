"""Reconcile the canonical Planner P-001..P-074 requirement inventory.

This gate proves inventory/traceability closure only. It deliberately does not
convert mock evidence, documentation references, or absent live evidence into a
PASS/SUPPORTED capability claim.
"""

from __future__ import annotations

import re
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKLOG = ROOT / "docs" / "backlog.md"
TRACEABILITY = ROOT / "docs" / "traceability.md"
EXPECTED_KEYS = tuple(f"P-{index:03d}" for index in range(1, 75))

_HEADING_RE = re.compile(r"^###\s+(P-\d{3})\b", re.MULTILINE)
_MENTION_RE = re.compile(r"P-(\d{3})(?:\.\.P-(\d{3}))?")


def _expand_mentions(text: str) -> set[str]:
    keys: set[str] = set()
    for start_text, end_text in _MENTION_RE.findall(text):
        start = int(start_text)
        end = int(end_text) if end_text else start
        if end < start:
            raise ValueError(f"descending Planner requirement range: P-{start:03d}..P-{end:03d}")
        keys.update(f"P-{index:03d}" for index in range(start, end + 1))
    return keys


def reconcile() -> tuple[str, ...]:
    """Return human-readable errors; an empty tuple is PASS."""
    backlog_text = BACKLOG.read_text(encoding="utf-8")
    traceability_text = TRACEABILITY.read_text(encoding="utf-8")
    expected = set(EXPECTED_KEYS)
    errors: list[str] = []

    headings = _HEADING_RE.findall(backlog_text)
    counts = Counter(headings)
    backlog_heading_keys = set(headings)
    missing_headings = sorted(expected - backlog_heading_keys)
    unexpected_headings = sorted(backlog_heading_keys - expected)
    duplicate_headings = sorted(key for key, count in counts.items() if count != 1)

    if missing_headings:
        errors.append(f"backlog missing canonical headings: {','.join(missing_headings)}")
    if unexpected_headings:
        errors.append(f"backlog has unexpected P-keys: {','.join(unexpected_headings)}")
    if duplicate_headings:
        errors.append(f"backlog has duplicate P-key headings: {','.join(duplicate_headings)}")
    if len(headings) != len(EXPECTED_KEYS):
        errors.append(f"backlog heading count is {len(headings)}, expected {len(EXPECTED_KEYS)}")

    traceability_keys = _expand_mentions(traceability_text)
    missing_traceability = sorted(expected - traceability_keys)
    unexpected_traceability = sorted(traceability_keys - expected)
    if missing_traceability:
        errors.append(
            "traceability missing Planner requirement coverage: "
            + ",".join(missing_traceability)
        )
    if unexpected_traceability:
        errors.append(
            "traceability references out-of-range Planner keys: "
            + ",".join(unexpected_traceability)
        )

    backlog_mentions = _expand_mentions(backlog_text)
    unexpected_backlog_mentions = sorted(backlog_mentions - expected)
    if unexpected_backlog_mentions:
        errors.append(
            "backlog references out-of-range Planner keys: "
            + ",".join(unexpected_backlog_mentions)
        )

    return tuple(errors)


def main() -> int:
    errors = reconcile()
    if errors:
        for error in errors:
            print(f"ERROR {error}")
        return 1
    print(
        "PASS planner requirement reconciliation "
        f"keys={len(EXPECTED_KEYS)} range={EXPECTED_KEYS[0]}..{EXPECTED_KEYS[-1]}"
    )
    print("NOTE inventory/traceability closure does not promote live capability state")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
