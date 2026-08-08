"""Reconciliation and lock skeleton tests."""

from __future__ import annotations

from planner_mcp.locks.types import LockType
from planner_mcp.reconciliation.model import DesiredResource, diff


def test_create_diff() -> None:
    desired = DesiredResource("plan-alpha", "plan", {"title": "Alpha"})
    change = diff(desired, None)
    assert change is not None and change.action == "create"


def test_no_diff_when_converged() -> None:
    desired = DesiredResource("plan-alpha", "plan", {"title": "Alpha"})
    assert diff(desired, {"title": "Alpha", "extra": 1}) is None


def test_update_diff_is_minimal() -> None:
    desired = DesiredResource("plan-alpha", "plan", {"title": "Beta", "x": 1})
    change = diff(desired, {"title": "Alpha", "x": 1})
    assert change is not None and change.fields == {"title": "Beta"}


def test_lock_types() -> None:
    assert LockType.PLAN.value == "plan"
    assert len(set(LockType)) == 5
