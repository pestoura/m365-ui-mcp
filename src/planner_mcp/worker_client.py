"""HTTP client for the private browser worker."""

from __future__ import annotations

from typing import Any

import httpx

from .config import Settings
from .errors import (
    ApprovalRequired,
    AuthRequired,
    BlockerConditionalAccess,
    PlannerMcpError,
    PolicyDenied,
    ProtocolIncompatible,
    UiContractUnattested,
    UiDrift,
    WorkerBusy,
    WorkerUnavailable,
)

_TYPED_HTTP_ERRORS: dict[str, tuple[type[PlannerMcpError], str]] = {
    "WORKER_BUSY": (WorkerBusy, "Browser profile admission capacity is exhausted"),
    "WORKER_UNAVAILABLE": (WorkerUnavailable, "Browser worker is unavailable"),
    "AUTH_REQUIRED": (AuthRequired, "Authentication is required"),
    "BLOCKER_CONDITIONAL_ACCESS": (
        BlockerConditionalAccess,
        "Conditional Access blocks this operation",
    ),
    "UI_CONTRACT_UNATTESTED": (
        UiContractUnattested,
        "Required UI contract is not attested",
    ),
    "UI_DRIFT": (UiDrift, "UI drift blocks this capability"),
    "POLICY_DENIED": (PolicyDenied, "Policy denied this semantic capability"),
    "APPROVAL_REQUIRED": (ApprovalRequired, "Approval is required"),
    "PROTOCOL_INCOMPATIBLE": (
        ProtocolIncompatible,
        "Control-plane and worker protocol versions are incompatible",
    ),
}


def _typed_worker_error(response: httpx.Response, *, path: str) -> PlannerMcpError | None:
    """Re-project only closed worker error codes from sanitized HTTP failures."""
    try:
        payload = response.json()
    except ValueError:
        return None
    if not isinstance(payload, dict):
        return None

    # Compatibility GET routes use FastAPI's {"detail": {...}} envelope. The
    # typed /operations boundary uses {"error": {"code": ...}}. Accept both,
    # but never propagate worker-supplied message/context values.
    detail = payload.get("detail")
    code: object = detail.get("error") if isinstance(detail, dict) else None
    if code is None:
        error = payload.get("error")
        code = error.get("code") if isinstance(error, dict) else None
    if not isinstance(code, str):
        return None

    projection = _TYPED_HTTP_ERRORS.get(code)
    if projection is None:
        return None
    error_type, message = projection
    return error_type(message, path=path)


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
        except httpx.HTTPStatusError as exc:
            typed = _typed_worker_error(exc.response, path=path)
            if typed is not None:
                raise typed from exc
            raise WorkerUnavailable(
                "browser worker request failed",
                path=path,
                status_code=exc.response.status_code,
            ) from exc
        except httpx.HTTPError as exc:
            raise WorkerUnavailable(
                "browser worker request failed",
                path=path,
                error=type(exc).__name__,
            ) from exc

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
