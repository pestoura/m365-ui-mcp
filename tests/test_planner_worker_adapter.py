from __future__ import annotations

import pytest

from m365_browser_worker.apps.planner import PlannerWorkerAdapter
from m365_browser_worker.protocol import (
    NoArguments,
    PlanArguments,
    TaskArguments,
    WorkerOperation,
    WorkerRequestEnvelope,
)
from planner_browser_worker import mock_data


def _adapter(*, mock: bool = True) -> tuple[PlannerWorkerAdapter, list[str]]:
    guarded: list[str] = []
    adapter = PlannerWorkerAdapter(
        is_mock=lambda: mock,
        capability_guard=guarded.append,
        data_provider=mock_data,
    )
    return adapter, guarded


def test_adapter_owns_exact_current_planner_worker_operations() -> None:
    expected = {
        WorkerOperation.PLANNER_PLAN_LIST,
        WorkerOperation.PLANNER_PLAN_GET,
        WorkerOperation.PLANNER_TASK_LIST,
        WorkerOperation.PLANNER_TASK_GET,
        WorkerOperation.PLANNER_PROJECT_SNAPSHOT,
    }

    owned = {
        operation for operation in WorkerOperation if PlannerWorkerAdapter.owns(operation)
    }
    assert owned == expected
    assert PlannerWorkerAdapter.owns(WorkerOperation.AUTH_STATUS) is False
    assert PlannerWorkerAdapter.owns(WorkerOperation.ACCOUNT_CONTEXT) is False


@pytest.mark.asyncio
async def test_mock_adapter_preserves_plan_and_task_read_outputs() -> None:
    adapter, guarded = _adapter()

    assert await adapter.plan_list() == {"plans": mock_data.PLANS}
    assert await adapter.plan_get("plan-alpha") == {"plan": mock_data.plan("plan-alpha")}
    assert await adapter.task_list("plan-alpha") == {
        "plan_id": "plan-alpha",
        "tasks": mock_data.tasks_for("plan-alpha"),
    }
    assert await adapter.task_get("task-1") == {"task": mock_data.task("task-1")}
    assert guarded == []


@pytest.mark.asyncio
async def test_mock_adapter_preserves_project_snapshot_shape() -> None:
    adapter, _guarded = _adapter()

    result = await adapter.project_snapshot("plan-alpha")
    tasks = mock_data.tasks_for("plan-alpha")

    assert result == {
        "plan": mock_data.plan("plan-alpha"),
        "tasks": tasks,
        "buckets": ["Backlog", "In Progress", "Done"],
        "counts": {"tasks": len(tasks)},
        "read_only": True,
    }


@pytest.mark.asyncio
async def test_live_adapter_preserves_capability_guards_and_safe_empty_reads() -> None:
    adapter, guarded = _adapter(mock=False)

    assert await adapter.plan_list() == {"plans": []}
    assert await adapter.plan_get("opaque-plan") == {"plan": None}
    assert await adapter.task_list("opaque-plan") == {"tasks": []}
    assert await adapter.task_get("opaque-task") == {"task": None}
    assert await adapter.project_snapshot("opaque-plan") == {
        "plan": None,
        "tasks": [],
    }
    assert guarded == [
        "plans.read",
        "plans.read",
        "tasks.read",
        "tasks.read",
        "project_snapshot.read",
    ]


@pytest.mark.asyncio
async def test_typed_dispatch_preserves_argument_scoping() -> None:
    adapter, _guarded = _adapter()

    plan_request = WorkerRequestEnvelope(
        request_id="req-plan",
        operation=WorkerOperation.PLANNER_PLAN_GET,
        arguments=PlanArguments(plan_id="plan-alpha"),
    )
    task_request = WorkerRequestEnvelope(
        request_id="req-task",
        operation=WorkerOperation.PLANNER_TASK_GET,
        arguments=TaskArguments(task_id="task-1"),
    )
    list_request = WorkerRequestEnvelope(
        request_id="req-list",
        operation=WorkerOperation.PLANNER_PLAN_LIST,
        arguments=NoArguments(),
    )

    assert await adapter.dispatch(plan_request) == {"plan": mock_data.plan("plan-alpha")}
    assert await adapter.dispatch(task_request) == {"task": mock_data.task("task-1")}
    assert await adapter.dispatch(list_request) == {"plans": mock_data.PLANS}
