"""Sanitized error projection for the private Microsoft 365 browser worker.

Only closed error codes and operation-derived application/capability metadata
cross the worker boundary. Raw exception text, arbitrary exception context,
URLs, selectors, tenant/account identifiers and session material are never
projected into typed worker errors.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Literal

from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field

from m365_browser_worker.protocol import PROTOCOL_SCHEMA_VERSION, WorkerOperation
from planner_mcp.errors import PlannerMcpError


class WorkerErrorCode(StrEnum):
    """Closed error vocabulary exposed by the typed worker boundary."""

    WORKER_ERROR = "WORKER_ERROR"
    WORKER_BUSY = "WORKER_BUSY"
    WORKER_UNAVAILABLE = "WORKER_UNAVAILABLE"
    AUTH_REQUIRED = "AUTH_REQUIRED"
    CONDITIONAL_ACCESS_BLOCKED = "BLOCKER_CONDITIONAL_ACCESS"
    UI_CONTRACT_UNATTESTED = "UI_CONTRACT_UNATTESTED"
    UI_DRIFT = "UI_DRIFT"
    POLICY_DENIED = "POLICY_DENIED"
    APPROVAL_REQUIRED = "APPROVAL_REQUIRED"
    PLAN_NOT_FOUND = "PLAN_NOT_FOUND"
    TASK_NOT_FOUND = "TASK_NOT_FOUND"
    PROTOCOL_INCOMPATIBLE = "PROTOCOL_INCOMPATIBLE"


class WorkerErrorDetail(BaseModel):
    """Bounded semantic error safe for control-plane consumption."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    code: WorkerErrorCode
    message: str = Field(min_length=1, max_length=160)
    retryable: bool
    application: Literal["planner"] | None = None
    capability: str | None = Field(default=None, max_length=128)


class WorkerErrorEnvelope(BaseModel):
    """Typed worker error response tied to the request/operation only."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["1"] = PROTOCOL_SCHEMA_VERSION
    request_id: str = Field(min_length=1, max_length=128)
    operation: WorkerOperation
    error: WorkerErrorDetail


@dataclass(frozen=True)
class _ErrorPolicy:
    code: WorkerErrorCode
    message: str
    status_code: int
    retryable: bool


_ERROR_POLICIES: dict[str, _ErrorPolicy] = {
    "WORKER_BUSY": _ErrorPolicy(
        WorkerErrorCode.WORKER_BUSY,
        "Browser profile admission capacity is exhausted",
        503,
        True,
    ),
    "WORKER_UNAVAILABLE": _ErrorPolicy(
        WorkerErrorCode.WORKER_UNAVAILABLE,
        "Browser worker is unavailable",
        503,
        True,
    ),
    "AUTH_REQUIRED": _ErrorPolicy(
        WorkerErrorCode.AUTH_REQUIRED,
        "Authentication is required",
        401,
        False,
    ),
    "BLOCKER_CONDITIONAL_ACCESS": _ErrorPolicy(
        WorkerErrorCode.CONDITIONAL_ACCESS_BLOCKED,
        "Conditional Access blocks this operation",
        403,
        False,
    ),
    "UI_CONTRACT_UNATTESTED": _ErrorPolicy(
        WorkerErrorCode.UI_CONTRACT_UNATTESTED,
        "Required UI contract is not attested",
        503,
        False,
    ),
    "UI_DRIFT": _ErrorPolicy(
        WorkerErrorCode.UI_DRIFT,
        "UI drift blocks this capability",
        503,
        False,
    ),
    "POLICY_DENIED": _ErrorPolicy(
        WorkerErrorCode.POLICY_DENIED,
        "Policy denied this semantic capability",
        403,
        False,
    ),
    "APPROVAL_REQUIRED": _ErrorPolicy(
        WorkerErrorCode.APPROVAL_REQUIRED,
        "Approval is required",
        409,
        False,
    ),
    "PLAN_NOT_FOUND": _ErrorPolicy(
        WorkerErrorCode.PLAN_NOT_FOUND,
        "Planner plan was not found",
        404,
        False,
    ),
    "TASK_NOT_FOUND": _ErrorPolicy(
        WorkerErrorCode.TASK_NOT_FOUND,
        "Planner task was not found",
        404,
        False,
    ),
    "PROTOCOL_INCOMPATIBLE": _ErrorPolicy(
        WorkerErrorCode.PROTOCOL_INCOMPATIBLE,
        "Control-plane and worker protocol versions are incompatible",
        503,
        False,
    ),
}
_DEFAULT_POLICY = _ErrorPolicy(
    WorkerErrorCode.WORKER_ERROR,
    "Worker operation failed",
    500,
    False,
)

_OPERATION_SCOPE: dict[WorkerOperation, tuple[Literal["planner"] | None, str | None]] = {
    WorkerOperation.AUTH_STATUS: (None, None),
    WorkerOperation.AUTH_START: (None, None),
    WorkerOperation.AUTH_RESUME: (None, None),
    WorkerOperation.AUTH_SESSION: (None, None),
    WorkerOperation.ACCOUNT_CONTEXT: (None, None),
    WorkerOperation.ACCOUNT_LICENSE: (None, None),
    WorkerOperation.PLANNER_PLAN_LIST: ("planner", "plans.read"),
    WorkerOperation.PLANNER_PLAN_GET: ("planner", "plans.read"),
    WorkerOperation.PLANNER_TASK_LIST: ("planner", "tasks.read"),
    WorkerOperation.PLANNER_TASK_GET: ("planner", "tasks.read"),
    WorkerOperation.PLANNER_PROJECT_SNAPSHOT: ("planner", "project_snapshot.read"),
}


def _source_code(exc: BaseException) -> str:
    if isinstance(exc, PlannerMcpError):
        return exc.code
    if isinstance(exc, HTTPException) and isinstance(exc.detail, dict):
        code = exc.detail.get("error")
        if isinstance(code, str):
            return code
    return "WORKER_ERROR"


def project_worker_error(
    exc: BaseException,
    *,
    request_id: str,
    operation: WorkerOperation,
) -> tuple[int, WorkerErrorEnvelope]:
    """Project an internal exception to a closed, context-safe worker error."""
    policy = _ERROR_POLICIES.get(_source_code(exc), _DEFAULT_POLICY)
    application, capability = _OPERATION_SCOPE[operation]
    return (
        policy.status_code,
        WorkerErrorEnvelope(
            request_id=request_id,
            operation=operation,
            error=WorkerErrorDetail(
                code=policy.code,
                message=policy.message,
                retryable=policy.retryable,
                application=application,
                capability=capability,
            ),
        ),
    )


__all__ = [
    "WorkerErrorCode",
    "WorkerErrorDetail",
    "WorkerErrorEnvelope",
    "project_worker_error",
]
