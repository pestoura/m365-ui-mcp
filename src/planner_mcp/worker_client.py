"""HTTP client for the private browser worker."""

from __future__ import annotations

from typing import Any

import httpx

from .config import Settings
from .errors import WorkerUnavailable


class WorkerClient:
    """Thin, timeout-bounded client. Never forwards secrets."""

    def __init__(self, settings: Settings) -> None:
        self._base = settings.worker_base_url.rstrip("/")
        self._timeout = settings.request_timeout_s

    async def _get(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        url = f"{self._base}{path}"
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.get(url, params=params)
                response.raise_for_status()
                data: dict[str, Any] = response.json()
                return data
        except httpx.HTTPError as exc:
            raise WorkerUnavailable("browser worker request failed", path=path,
                                    error=type(exc).__name__) from exc

    async def health(self) -> dict[str, Any]:
        return await self._get("/health")

    async def auth_status(self) -> dict[str, Any]:
        return await self._get("/auth/status")

    async def auth_start(self) -> dict[str, Any]:
        return await self._get("/auth/start")

    async def auth_resume(self) -> dict[str, Any]:
        return await self._get("/auth/resume")

    async def session_info(self) -> dict[str, Any]:
        return await self._get("/auth/session")

    async def account_context(self) -> dict[str, Any]:
        return await self._get("/account/context")

    async def license_capabilities(self) -> dict[str, Any]:
        return await self._get("/account/license")

    async def plan_list(self) -> dict[str, Any]:
        return await self._get("/planner/plans")

    async def plan_get(self, plan_id: str) -> dict[str, Any]:
        return await self._get(f"/planner/plans/{plan_id}")

    async def task_list(self, plan_id: str) -> dict[str, Any]:
        return await self._get("/planner/tasks", params={"plan_id": plan_id})

    async def task_get(self, task_id: str) -> dict[str, Any]:
        return await self._get(f"/planner/tasks/{task_id}")

    async def project_snapshot(self, plan_id: str) -> dict[str, Any]:
        return await self._get(f"/planner/plans/{plan_id}/snapshot")
