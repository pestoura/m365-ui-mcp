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
async def test_live_adapter_fails_closed_without_live_page() -> None:
    # In live mode (not mock) and without a live Planner page, every read-only
    # delivery capability fails closed with HTTP 503 rather than returning an
    # empty/synthetic surface. This is the fail-closed discipline: the read
    # path performs REAL extraction against the verified authenticated surface,
    # so without that surface there is nothing to read.
    adapter, guarded = _adapter(mock=False)

    from fastapi import HTTPException

    with pytest.raises(HTTPException):
        await adapter.plan_list()
    with pytest.raises(HTTPException):
        await adapter.plan_get("opaque-plan")
    with pytest.raises(HTTPException):
        await adapter.task_list("opaque-plan")
    with pytest.raises(HTTPException):
        await adapter.task_get("opaque-task")
    with pytest.raises(HTTPException):
        await adapter.project_snapshot("opaque-plan")
    # capability guard is consulted on each demand path.
    assert guarded == [
        "plans.read",
        "plans.read",
        "tasks.read",
        "tasks.read",
        "project_snapshot.read",
    ]


@pytest.mark.asyncio
async def test_live_adapter_reads_real_surface_with_live_page() -> None:
    # When a live Planner page is supplied, the live read path extracts the real
    # rendered surface (no fixture, no Graph API). This mirrors the five-reads
    # contract: only the three read-only delivery capabilities return live data.

    class _FakePage:
        def __init__(self, surface: dict[str, object]) -> None:
            self._surface = surface

        async def evaluate(self, _js: str) -> dict[str, object]:
            return self._surface

    class _FakeReader:
        def __init__(self, page: _FakePage | None) -> None:
            self._page = page

        def __call__(self) -> _FakePage | None:
            return self._page

    surface = {
        "surface_title": "Planner",
        "anchor_titles": ["UCS – Segurança Técnica", "Outro Plano", "Sign in"],
        "row_titles": ["Definir política", "Rever relatório", "Fechar ticket"],
        "visible_lines": ["UCS – Segurança Técnica", "Definir política", "Rever relatório"],
        "has_ucs": True,
        "has_seguranca": True,
    }

    class _NoopProvider:
        PLANS: list[dict[str, object]] = []

        def plan(self, plan_id: str):
            return None

        def tasks_for(self, plan_id: str):
            return []

        def task(self, task_id: str):
            return None

    adapter = PlannerWorkerAdapter(
        is_mock=lambda: False,
        capability_guard=lambda capability: None,
        data_provider=_NoopProvider(),
        live_reader=_FakeReader(_FakePage(surface)),
    )

    plan_list = await adapter.plan_list()
    assert plan_list["source"] == "live_ui"
    assert plan_list["read_only"] is True
    titles = {p["title"] for p in plan_list["plans"]}
    assert "UCS – Segurança Técnica" in titles
    assert "Sign in" not in titles

    plan = await adapter.plan_get("ucs-seguranca-tecnica")
    assert plan["plan"]["title"] == "UCS – Segurança Técnica"
    assert plan["read_only"] is True

    tasks = (await adapter.task_list("ucs-seguranca-tecnica"))["tasks"]
    assert len(tasks) == 3
    assert tasks[0]["title"] == "Definir política"

    snap = await adapter.project_snapshot("ucs-seguranca-tecnica")
    assert snap["plan"]["title"] == "UCS – Segurança Técnica"
    assert snap["counts"]["tasks"] == 3
    assert snap["read_only"] is True


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
