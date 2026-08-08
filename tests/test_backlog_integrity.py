"""Backlog integrity tests (backlog P-001, P-071).

Guards the canonical guardrail: P-001..P-074, epic grouping, critical path and
zero-padded dependencies must stay intact.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKLOG = (ROOT / "docs" / "backlog.md").read_text(encoding="utf-8")

EPIC_GROUPS = {
    "EPIC-01": (1, 10),
    "EPIC-02": (11, 17),
    "EPIC-03": (18, 24),
    "EPIC-04": (25, 30),
    "EPIC-05": (31, 36),
    "EPIC-06": (37, 45),
    "EPIC-07": (46, 53),
    "EPIC-08": (54, 60),
    "EPIC-09": (61, 67),
    "EPIC-10": (68, 74),
}

CRITICAL_PATH = [
    "P-001",
    "P-011",
    "P-014",
    "P-018",
    "P-025",
    "P-026",
    "P-027",
    "P-030",
    "P-031",
    "P-050",
    "P-069",
    "P-071",
    "P-073",
    "P-074",
]


def _item_keys() -> list[str]:
    return re.findall(r"^### (P-\d{3}) — ", BACKLOG, flags=re.MULTILINE)


def test_all_74_keys_present_and_unique() -> None:
    keys = _item_keys()
    assert len(keys) == 74, f"expected 74 backlog items, found {len(keys)}"
    assert len(set(keys)) == 74, "duplicate backlog keys"
    assert keys == [f"P-{i:03d}" for i in range(1, 75)], "keys are not in order P-001..P-074"


def test_epic_groups_present() -> None:
    for epic in EPIC_GROUPS:
        assert f"## {epic} —" in BACKLOG or f"| {epic} |" in BACKLOG, f"missing {epic}"


def test_epic_key_ranges_are_contiguous() -> None:
    for epic, (lo, hi) in EPIC_GROUPS.items():
        expected = f"P-{lo:03d}..P-{hi:03d}"
        assert expected in BACKLOG, f"{epic} range {expected} not declared"


def test_critical_path_declared_in_order() -> None:
    joined = " → ".join(CRITICAL_PATH)
    normalized = BACKLOG.replace("`", "").replace("\n", " ")
    normalized = re.sub(r"\s+", " ", normalized)
    assert joined in normalized, "critical path is missing or out of order"


def test_every_item_has_required_sections() -> None:
    blocks = re.split(r"^### P-\d{3} — ", BACKLOG, flags=re.MULTILINE)[1:]
    assert len(blocks) == 74
    for i, block in enumerate(blocks, start=1):
        for field in (
            "**Objective:**",
            "**Scope:**",
            "**Acceptance:**",
            "**Tests/gates:**",
            "**Depends:**",
            "**Evidence:**",
        ):
            assert field in block, f"P-{i:03d} missing {field}"


def test_dependencies_are_zero_padded_and_valid() -> None:
    refs = re.findall(r"P-(\d+)", BACKLOG)
    for ref in refs:
        assert len(ref) == 3, f"non zero-padded key reference: P-{ref}"
        assert 1 <= int(ref) <= 74, f"out-of-range key: P-{ref}"


def test_dependency_summary_covers_every_key() -> None:
    tail = BACKLOG.split("## Dependency summary", 1)[1]
    for i in range(1, 75):
        assert f"| P-{i:03d} |" in tail, f"P-{i:03d} missing from dependency summary"
