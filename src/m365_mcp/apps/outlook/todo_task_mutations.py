"""Synthetic-only Outlook To Do task mutations for OUT-104.

The module mutates bounded in-memory semantic task state only. It never exposes
Microsoft Graph, browser selectors, addresses, URLs, sessions, tokens or live
tenant material.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from m365_mcp.apps.outlook.mock_ui import OutlookMockFixture
from m365_mcp.apps.outlook.readiness import OutlookReadinessReport
from m365_mcp.apps.outlook.todo_task_reads import (
    SyntheticTodoList,
    SyntheticTodoTask,
    TaskState,
)

_MAX_TASKS = 500


class TodoTaskAction(StrEnum):
    CREATE = "CREATE"
    UPDATE = "UPDATE"
    COMPLETE = "COMPLETE"
    DELETE = "DELETE"


def _validate_key(name: str, value: str) -> None:
    if not value or value != value.strip() or "@" in value or any(
        char.isspace() for char in value
    ):
        raise ValueError(f"{name} must be an opaque semantic token")


@dataclass(frozen=True)
class TodoTaskMutationRequest:
    action: TodoTaskAction
    task_key: str
    list_key: str | None = None
    title: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.action, TodoTaskAction):
            raise ValueError("action must be a closed TodoTaskAction")
        _validate_key("task_key", self.task_key)
        if self.list_key is not None:
            _validate_key("list_key", self.list_key)
        if self.action in (TodoTaskAction.CREATE, TodoTaskAction.UPDATE):
            if not self.list_key:
                raise ValueError("create/update requires list_key")
            if not self.title or self.title != self.title.strip():
                raise ValueError("create/update requires a non-empty trimmed title")


@dataclass(frozen=True)
class TodoTaskMutationResult:
    action: TodoTaskAction
    task_key: str
    existed_before: bool
    exists_after: bool
    changed: bool
    read_back: SyntheticTodoTask | None
    verified: bool
    synthetic: bool


def _gate(fixture: OutlookMockFixture, readiness: OutlookReadinessReport) -> None:
    if not fixture.synthetic:
        raise ValueError("OUT-104 fixture execution requires synthetic=true")
    if not readiness.ready_for_readonly_discovery:
        raise ValueError("Outlook read-only discovery is not ready")


def _validate_catalog(
    lists: tuple[SyntheticTodoList, ...],
    tasks: tuple[SyntheticTodoTask, ...],
) -> None:
    if len(tasks) > _MAX_TASKS:
        raise ValueError("task catalog exceeds bounded size")
    list_keys = {item.list_key for item in lists}
    if len(list_keys) != len(lists):
        raise ValueError("todo list keys must be unique")
    task_keys = tuple(item.task_key for item in tasks)
    if len(set(task_keys)) != len(task_keys):
        raise ValueError("task keys must be unique")
    if any(item.list_key not in list_keys for item in tasks):
        raise ValueError("task references unknown list_key")


def apply_todo_task_mutation(
    fixture: OutlookMockFixture,
    lists: tuple[SyntheticTodoList, ...],
    tasks: tuple[SyntheticTodoTask, ...],
    request: TodoTaskMutationRequest,
    *,
    readiness: OutlookReadinessReport,
) -> tuple[tuple[SyntheticTodoTask, ...], TodoTaskMutationResult]:
    """Apply one bounded task mutation and prove exact local read-back."""
    _gate(fixture, readiness)
    _validate_catalog(lists, tasks)
    existing = next(
        (item for item in tasks if item.task_key == request.task_key),
        None,
    )
    list_keys = {item.list_key for item in lists}

    if request.action is TodoTaskAction.CREATE:
        assert request.list_key is not None
        if request.list_key not in list_keys:
            raise ValueError("synthetic list_key not found")
        desired = SyntheticTodoTask(
            request.task_key,
            request.list_key,
            request.title or "",
            TaskState.NOT_STARTED,
        )
        if existing is None:
            if len(tasks) >= _MAX_TASKS:
                raise ValueError("task catalog exceeds bounded size")
            updated = tasks + (desired,)
            changed = True
        elif existing == desired:
            updated = tasks
            changed = False
        else:
            raise ValueError("task_key already exists with different state")
        expected: SyntheticTodoTask | None = desired
    elif request.action is TodoTaskAction.UPDATE:
        if existing is None:
            raise ValueError("synthetic task_key not found")
        assert request.list_key is not None
        if request.list_key not in list_keys:
            raise ValueError("synthetic list_key not found")
        desired = SyntheticTodoTask(
            request.task_key,
            request.list_key,
            request.title or "",
            existing.state,
            existing.due_day_offset,
        )
        updated = tuple(
            desired if item.task_key == request.task_key else item for item in tasks
        )
        changed = desired != existing
        expected = desired
    elif request.action is TodoTaskAction.COMPLETE:
        if existing is None:
            raise ValueError("synthetic task_key not found")
        desired = SyntheticTodoTask(
            existing.task_key,
            existing.list_key,
            existing.title,
            TaskState.COMPLETED,
            existing.due_day_offset,
        )
        updated = tuple(
            desired if item.task_key == request.task_key else item for item in tasks
        )
        changed = desired != existing
        expected = desired
    elif request.action is TodoTaskAction.DELETE:
        updated = tuple(item for item in tasks if item.task_key != request.task_key)
        changed = existing is not None
        expected = None
    else:
        raise ValueError("unsupported task mutation")

    updated = tuple(sorted(updated, key=lambda item: item.task_key))
    _validate_catalog(lists, updated)
    read_back = next(
        (item for item in updated if item.task_key == request.task_key),
        None,
    )
    if read_back != expected:
        raise RuntimeError("task read-back did not prove requested state")
    return updated, TodoTaskMutationResult(
        action=request.action,
        task_key=request.task_key,
        existed_before=existing is not None,
        exists_after=read_back is not None,
        changed=changed,
        read_back=read_back,
        verified=True,
        synthetic=True,
    )


__all__ = [
    "TodoTaskAction",
    "TodoTaskMutationRequest",
    "TodoTaskMutationResult",
    "apply_todo_task_mutation",
]
