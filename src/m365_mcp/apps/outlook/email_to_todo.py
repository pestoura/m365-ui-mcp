"""Synthetic-only email-to-To Do composite for OUT-110."""

from __future__ import annotations

from dataclasses import dataclass

from m365_mcp.apps.outlook.message_get import MessageGetRequest, get_fixture_message
from m365_mcp.apps.outlook.mock_ui import OutlookMockFixture
from m365_mcp.apps.outlook.readiness import OutlookReadinessReport
from m365_mcp.apps.outlook.todo_task_mutations import (
    TodoTaskAction,
    TodoTaskMutationRequest,
    TodoTaskMutationResult,
    apply_todo_task_mutation,
)
from m365_mcp.apps.outlook.todo_task_reads import SyntheticTodoList, SyntheticTodoTask


@dataclass(frozen=True)
class EmailToTodoRequest:
    message_key: str
    task_key: str
    list_key: str

    def __post_init__(self) -> None:
        for name in ("message_key", "task_key", "list_key"):
            value = getattr(self, name)
            if (
                not value
                or value != value.strip()
                or "@" in value
                or any(char.isspace() for char in value)
            ):
                raise ValueError(f"{name} must be an opaque semantic token")


@dataclass(frozen=True)
class EmailToTodoResult:
    source_message_key: str
    task_key: str
    task_result: TodoTaskMutationResult
    source_read_verified: bool
    verified: bool
    synthetic: bool = True


def create_todo_from_email(
    fixture: OutlookMockFixture,
    lists: tuple[SyntheticTodoList, ...],
    tasks: tuple[SyntheticTodoTask, ...],
    request: EmailToTodoRequest,
    *,
    readiness: OutlookReadinessReport,
) -> tuple[tuple[SyntheticTodoTask, ...], EmailToTodoResult]:
    """Read one synthetic message and create an idempotent task from its subject."""
    source = get_fixture_message(
        fixture,
        MessageGetRequest(request.message_key),
        readiness=readiness,
    )
    updated, task_result = apply_todo_task_mutation(
        fixture,
        lists,
        tasks,
        TodoTaskMutationRequest(
            action=TodoTaskAction.CREATE,
            task_key=request.task_key,
            list_key=request.list_key,
            title=source.subject,
        ),
        readiness=readiness,
    )
    read_back = task_result.read_back
    if read_back is None or read_back.title != source.subject:
        raise RuntimeError("email-to-task read-back did not prove source projection")
    return updated, EmailToTodoResult(
        source_message_key=source.message_key,
        task_key=request.task_key,
        task_result=task_result,
        source_read_verified=True,
        verified=True,
    )


__all__ = ["EmailToTodoRequest", "EmailToTodoResult", "create_todo_from_email"]
