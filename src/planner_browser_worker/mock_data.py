"""Deterministic mock Planner data. Used by CI; never touches real Planner."""

from __future__ import annotations

from typing import Any

PLANS: list[dict[str, Any]] = [
    {
        "id": "plan-alpha",
        "external_id": "plan-alpha",
        "source_id": "mock:plan:1",
        "title": "Alpha Programme",
        "premium": True,
        "buckets": ["Backlog", "In Progress", "Done"],
    },
    {
        "id": "plan-beta",
        "external_id": "plan-beta",
        "source_id": "mock:plan:2",
        "title": "Beta Rollout",
        "premium": True,
        "buckets": ["Todo", "Doing"],
    },
]

TASKS: list[dict[str, Any]] = [
    {
        "id": "task-1",
        "plan_id": "plan-alpha",
        "external_id": "task-1",
        "source_id": "mock:task:1",
        "title": "Define UIContract attestation procedure",
        "bucket": "In Progress",
        "percent_complete": 50,
        "dependencies": [],
    },
    {
        "id": "task-2",
        "plan_id": "plan-alpha",
        "external_id": "task-2",
        "source_id": "mock:task:2",
        "title": "Draft threat model",
        "bucket": "Backlog",
        "percent_complete": 0,
        "dependencies": ["task-1"],
    },
    {
        "id": "task-3",
        "plan_id": "plan-beta",
        "external_id": "task-3",
        "source_id": "mock:task:3",
        "title": "Pilot tenant readiness",
        "bucket": "Doing",
        "percent_complete": 20,
        "dependencies": [],
    },
]

ACCOUNT_CONTEXT: dict[str, Any] = {
    "tenant_display": "mock-tenant",
    "account_kind": "work_or_school",
    "user_identifier": "[REDACTED]",
    "profile": "professional-isolated",
    "device_enrolment": "none",
}

LICENSE: dict[str, Any] = {
    "premium_detected": True,
    "evidence": "mock-ui-license-banner",
    "graph_api_used": False,
}


def plan(plan_id: str) -> dict[str, Any] | None:
    """Return one mock plan."""
    return next((p for p in PLANS if p["id"] == plan_id), None)


def tasks_for(plan_id: str) -> list[dict[str, Any]]:
    """Return mock tasks for a plan."""
    return [t for t in TASKS if t["plan_id"] == plan_id]


def task(task_id: str) -> dict[str, Any] | None:
    """Return one mock task."""
    return next((t for t in TASKS if t["id"] == task_id), None)
