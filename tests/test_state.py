"""SQLite state foundation tests."""

from __future__ import annotations

from pathlib import Path

from planner_mcp.state import closing_connection, health, initialise


def test_pragmas_and_schema(state_path: Path) -> None:
    initialise(state_path)
    report = health(state_path)
    assert report["ok"] is True
    assert str(report["journal_mode"]).lower() == "wal"
    assert report["foreign_keys"] is True


def test_foreign_keys_enforced(state_path: Path) -> None:
    initialise(state_path)
    with closing_connection(state_path) as conn:
        rows = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    names = {row["name"] for row in rows}
    assert {"resource", "resource_lock", "idempotency", "saga",
            "checkpoint", "approval", "audit_event"} <= names


def test_initialise_is_idempotent(state_path: Path) -> None:
    initialise(state_path)
    initialise(state_path)
    assert health(state_path)["ok"] is True
