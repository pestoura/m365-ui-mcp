"""Closed typed semantic protocol for the private Microsoft 365 browser worker.

The protocol accepts only registered semantic operations. It intentionally has
no URL, selector, XPath, JavaScript, header, cookie, token or storage-state
primitive. Protocol version negotiation is a separate CORE-029 concern.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

PROTOCOL_SCHEMA_VERSION = "1"


class WorkerOperation(StrEnum):
    """Closed operation vocabulary supported by the current worker surface."""

    AUTH_STATUS = "auth.status"
    AUTH_START = "auth.start"
    AUTH_RESUME = "auth.resume"
    AUTH_SESSION = "auth.session"
    ACCOUNT_CONTEXT = "account.context"
    ACCOUNT_LICENSE = "account.license"
    PLANNER_PLAN_LIST = "planner.plan.list"
    PLANNER_PLAN_GET = "planner.plan.get"
    PLANNER_TASK_LIST = "planner.task.list"
    PLANNER_TASK_GET = "planner.task.get"
    PLANNER_PROJECT_SNAPSHOT = "planner.project.snapshot"


class _ProtocolModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class NoArguments(_ProtocolModel):
    """Explicit empty argument shape for operations that accept no input."""

    kind: Literal["none"] = "none"


class PlanArguments(_ProtocolModel):
    """Arguments scoped to a single Planner plan."""

    kind: Literal["plan"] = "plan"
    plan_id: str = Field(min_length=1, max_length=256)


class TaskArguments(_ProtocolModel):
    """Arguments scoped to a single Planner task."""

    kind: Literal["task"] = "task"
    task_id: str = Field(min_length=1, max_length=256)


WorkerArguments = Annotated[
    NoArguments | PlanArguments | TaskArguments,
    Field(discriminator="kind"),
]

_NO_ARGUMENT_OPERATIONS = frozenset(
    {
        WorkerOperation.AUTH_STATUS,
        WorkerOperation.AUTH_START,
        WorkerOperation.AUTH_RESUME,
        WorkerOperation.AUTH_SESSION,
        WorkerOperation.ACCOUNT_CONTEXT,
        WorkerOperation.ACCOUNT_LICENSE,
        WorkerOperation.PLANNER_PLAN_LIST,
    }
)
_PLAN_ARGUMENT_OPERATIONS = frozenset(
    {
        WorkerOperation.PLANNER_PLAN_GET,
        WorkerOperation.PLANNER_TASK_LIST,
        WorkerOperation.PLANNER_PROJECT_SNAPSHOT,
    }
)
_TASK_ARGUMENT_OPERATIONS = frozenset({WorkerOperation.PLANNER_TASK_GET})


class WorkerRequestEnvelope(_ProtocolModel):
    """Validated request envelope for one closed semantic worker operation."""

    schema_version: Literal["1"] = PROTOCOL_SCHEMA_VERSION
    request_id: str = Field(min_length=1, max_length=128)
    operation: WorkerOperation
    arguments: WorkerArguments

    @model_validator(mode="after")
    def validate_operation_arguments(self) -> WorkerRequestEnvelope:
        """Reject operation/argument mismatches rather than coercing them."""
        if self.operation in _NO_ARGUMENT_OPERATIONS and not isinstance(
            self.arguments, NoArguments
        ):
            raise ValueError("operation requires no arguments")
        if self.operation in _PLAN_ARGUMENT_OPERATIONS and not isinstance(
            self.arguments, PlanArguments
        ):
            raise ValueError("operation requires plan arguments")
        if self.operation in _TASK_ARGUMENT_OPERATIONS and not isinstance(
            self.arguments, TaskArguments
        ):
            raise ValueError("operation requires task arguments")
        return self


class WorkerResponseEnvelope(_ProtocolModel):
    """Success envelope carrying only the semantic operation result."""

    schema_version: Literal["1"] = PROTOCOL_SCHEMA_VERSION
    request_id: str = Field(min_length=1, max_length=128)
    operation: WorkerOperation
    result: dict[str, object]


FORBIDDEN_PROTOCOL_FIELDS = frozenset(
    {
        "url",
        "selector",
        "xpath",
        "javascript",
        "script",
        "headers",
        "cookie",
        "cookies",
        "token",
        "storage_state",
    }
)


__all__ = [
    "FORBIDDEN_PROTOCOL_FIELDS",
    "PROTOCOL_SCHEMA_VERSION",
    "NoArguments",
    "PlanArguments",
    "TaskArguments",
    "WorkerArguments",
    "WorkerOperation",
    "WorkerRequestEnvelope",
    "WorkerResponseEnvelope",
]
