"""Planner-owned browser-worker operations for PLN-MIG-005.

The adapter owns Planner semantic worker behavior while the legacy
``planner_browser_worker`` FastAPI package remains a compatibility shell. It is
parameterized by a data provider and capability guard so the generic worker
core does not import Planner legacy packages or tenant data.
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

    def __init__(
        self,
        *,
        is_mock: Callable[[], bool],
        capability_guard: Callable[[str], None],
        data_provider: PlannerDataProvider,
    ) -> None:
        self._is_mock = is_mock
        self._capability_guard = capability_guard
        self._data = data_provider

    @classmethod
    def owns(cls, operation: WorkerOperation) -> bool:
        """Return whether the operation belongs to the Planner adapter."""
        return operation in cls._OPERATIONS

    async def plan_list(self) -> dict[str, Any]:
        if self._is_mock():
            return {"plans": self._data.PLANS}
        self._capability_guard("plans.read")
        return {"plans": []}

    async def plan_get(self, plan_id: str) -> dict[str, Any]:
        if not self._is_mock():
            self._capability_guard("plans.read")
            return {"plan": None}
        plan = self._data.plan(plan_id)
        if plan is None:
            raise HTTPException(status_code=404, detail={"error": "PLAN_NOT_FOUND"})
        return {"plan": plan}

    async def task_list(self, plan_id: str) -> dict[str, Any]:
        if not self._is_mock():
            self._capability_guard("tasks.read")
            return {"tasks": []}
        return {"plan_id": plan_id, "tasks": self._data.tasks_for(plan_id)}

    async def task_get(self, task_id: str) -> dict[str, Any]:
        if not self._is_mock():
            self._capability_guard("tasks.read")
            return {"task": None}
        task = self._data.task(task_id)
        if task is None:
            raise HTTPException(status_code=404, detail={"error": "TASK_NOT_FOUND"})
        return {"task": task}

    async def project_snapshot(self, plan_id: str) -> dict[str, Any]:
        if not self._is_mock():
            self._capability_guard("project_snapshot.read")
            return {"plan": None, "tasks": []}
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
