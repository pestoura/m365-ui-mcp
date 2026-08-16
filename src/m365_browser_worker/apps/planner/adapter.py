"""Planner-owned browser-worker operations for PLN-MIG-005.

The adapter owns Planner semantic worker behavior while the legacy
``planner_browser_worker`` FastAPI package remains a compatibility shell. It is
parameterized by a data provider and capability guard so the generic worker
core does not import Planner legacy packages or tenant data.

First-delivery LIVE reads perform REAL Playwright extraction against the already
authenticated Planner Web surface. They are read-only (a single sanitized in-page
text read per call) and require the broker authorization gate (verified
professional session) to have already passed via ``capability_guard``. No UIContract
fragment attestation is required for the read path; the authenticated surface is the
authorization boundary.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, Protocol

from fastapi import HTTPException

from m365_browser_worker.protocol import (
    PlanArguments,
    TaskArguments,
    WorkerOperation,
    WorkerRequestEnvelope,
)


class PlannerDataProvider(Protocol):
    """Minimal mock/read provider consumed by the Planner worker adapter."""

    PLANS: list[dict[str, Any]]

    def plan(self, plan_id: str) -> dict[str, Any] | None: ...

    def tasks_for(self, plan_id: str) -> list[dict[str, Any]]: ...

    def task(self, task_id: str) -> dict[str, Any] | None: ...


class PlannerWorkerAdapter:
    """Closed Planner semantic worker adapter with no generic browser primitive."""

    _OPERATIONS = frozenset(
        {
            WorkerOperation.PLANNER_PLAN_LIST,
            WorkerOperation.PLANNER_PLAN_GET,
            WorkerOperation.PLANNER_TASK_LIST,
            WorkerOperation.PLANNER_TASK_GET,
            WorkerOperation.PLANNER_PROJECT_SNAPSHOT,
        }
    )

    # The three read-only delivery capabilities. These are authorized by the
    # session broker (verified professional surface), NOT by UIContract fragment
    # attestation, so they can be performed as live UI reads without inventing
    # selectors (CORE-019). All other capabilities remain fail-closed.
    _LIVE_READ_CAPABILITIES = frozenset(
        {"plans.read", "tasks.read", "project_snapshot.read"}
    )

    def __init__(
        self,
        *,
        is_mock: Callable[[], bool],
        capability_guard: Callable[[str], None],
        data_provider: PlannerDataProvider,
        live_reader: Callable[[], Any] | None = None,
    ) -> None:
        self._is_mock = is_mock
        self._capability_guard = capability_guard
        self._data = data_provider
        self._live_reader = live_reader

    @classmethod
    def owns(cls, operation: WorkerOperation) -> bool:
        """Return whether the operation belongs to the Planner adapter."""
        return operation in cls._OPERATIONS

    def _live_page(self) -> Any:
        """Return the authenticated live Planner page, failing closed otherwise."""
        if self._live_reader is None:
            raise HTTPException(
                status_code=503,
                detail={"error": "LIVE_READ_PATH_UNAVAILABLE"},
            )
        page = self._live_reader()
        if page is None:
            raise HTTPException(
                status_code=503,
                detail={"error": "NO_LIVE_PLANNER_PAGE"},
            )
        return page

    async def plan_list(self) -> dict[str, Any]:
        if self._is_mock():
            return {"plans": self._data.PLANS}
        self._capability_guard("plans.read")
        from m365_browser_worker.apps.planner.live_read import extract_plans

        page = self._live_page()
        plans = await extract_plans(page)
        return {"plans": plans, "source": "live_ui", "read_only": True}

    async def plan_get(self, plan_id: str) -> dict[str, Any]:
        if self._is_mock():
            plan = self._data.plan(plan_id)
            if plan is None:
                raise HTTPException(status_code=404, detail={"error": "PLAN_NOT_FOUND"})
            return {"plan": plan}
        self._capability_guard("plans.read")
        from m365_browser_worker.apps.planner.live_read import extract_plan

        page = self._live_page()
        plan = await extract_plan(page, plan_id)
        if plan is None:
            raise HTTPException(status_code=404, detail={"error": "PLAN_NOT_FOUND"})
        return {"plan": plan, "source": "live_ui", "read_only": True}

    async def task_list(self, plan_id: str) -> dict[str, Any]:
        if self._is_mock():
            return {"plan_id": plan_id, "tasks": self._data.tasks_for(plan_id)}
        self._capability_guard("tasks.read")
        from m365_browser_worker.apps.planner.live_read import extract_tasks

        page = self._live_page()
        tasks = await extract_tasks(page, plan_id)
        return {
            "plan_id": plan_id,
            "tasks": tasks,
            "source": "live_ui",
            "read_only": True,
        }

    async def task_get(self, task_id: str) -> dict[str, Any]:
        if self._is_mock():
            task = self._data.task(task_id)
            if task is None:
                raise HTTPException(status_code=404, detail={"error": "TASK_NOT_FOUND"})
            return {"task": task}
        self._capability_guard("tasks.read")
        from m365_browser_worker.apps.planner.live_read import extract_task

        page = self._live_page()
        task = await extract_task(page, task_id)
        if task is None:
            raise HTTPException(status_code=404, detail={"error": "TASK_NOT_FOUND"})
        return {"task": task, "source": "live_ui", "read_only": True}

    async def project_snapshot(self, plan_id: str) -> dict[str, Any]:
        if self._is_mock():
            plan = self._data.plan(plan_id)
            if plan is None:
                raise HTTPException(status_code=404, detail={"error": "PLAN_NOT_FOUND"})
            tasks = self._data.tasks_for(plan_id)
            return {
                "plan": plan,
                "tasks": tasks,
                "buckets": plan.get("buckets", []),
                "counts": {"tasks": len(tasks)},
                "read_only": True,
            }
        self._capability_guard("project_snapshot.read")
        from m365_browser_worker.apps.planner.live_read import extract_snapshot

        page = self._live_page()
        snapshot = await extract_snapshot(page, plan_id)
        return snapshot

    async def dispatch(self, request: WorkerRequestEnvelope) -> dict[str, Any]:
        """Dispatch one Planner-owned typed operation, failing closed otherwise."""
        operation = request.operation
        arguments = request.arguments

        if operation is WorkerOperation.PLANNER_PLAN_LIST:
            return await self.plan_list()
        if operation is WorkerOperation.PLANNER_PLAN_GET:
            if not isinstance(arguments, PlanArguments):
                raise HTTPException(status_code=422, detail="plan arguments required")
            return await self.plan_get(arguments.plan_id)
        if operation is WorkerOperation.PLANNER_TASK_LIST:
            if not isinstance(arguments, PlanArguments):
                raise HTTPException(status_code=422, detail="plan arguments required")
            return await self.task_list(arguments.plan_id)
        if operation is WorkerOperation.PLANNER_TASK_GET:
            if not isinstance(arguments, TaskArguments):
                raise HTTPException(status_code=422, detail="task arguments required")
            return await self.task_get(arguments.task_id)
        if operation is WorkerOperation.PLANNER_PROJECT_SNAPSHOT:
            if not isinstance(arguments, PlanArguments):
                raise HTTPException(status_code=422, detail="plan arguments required")
            return await self.project_snapshot(arguments.plan_id)

        raise HTTPException(status_code=422, detail="unsupported Planner worker operation")


__all__ = ["PlannerDataProvider", "PlannerWorkerAdapter"]
