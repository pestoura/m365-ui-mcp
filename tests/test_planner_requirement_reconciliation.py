from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "check_planner_requirement_reconciliation.py"


def _load_checker() -> ModuleType:
    spec = importlib.util.spec_from_file_location("planner_requirement_reconciliation", SCRIPT)
    if spec is None or spec.loader is None:
        raise AssertionError("unable to load Planner requirement reconciliation checker")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_planner_requirement_inventory_and_traceability_are_closed() -> None:
    checker = _load_checker()

    assert checker.EXPECTED_KEYS[0] == "P-001"
    assert checker.EXPECTED_KEYS[-1] == "P-074"
    assert len(checker.EXPECTED_KEYS) == 74
    assert checker.reconcile() == ()


def test_checker_expands_bounded_requirement_ranges() -> None:
    checker = _load_checker()

    assert checker._expand_mentions("P-001, P-003..P-005") == {
        "P-001",
        "P-003",
        "P-004",
        "P-005",
    }


def test_checker_rejects_descending_requirement_ranges() -> None:
    checker = _load_checker()

    try:
        checker._expand_mentions("P-010..P-009")
    except ValueError as exc:
        assert "descending Planner requirement range" in str(exc)
    else:
        raise AssertionError("descending requirement range must fail closed")
