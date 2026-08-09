"""Synthetic-only Outlook To Do Important/My Day mutations for OUT-106."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from m365_mcp.apps.outlook.mock_ui import OutlookMockFixture
from m365_mcp.apps.outlook.readiness import OutlookReadinessReport
from m365_mcp.apps.outlook.todo_task_reads import SyntheticTodoTask, TaskState


class TodoFocusAction(StrEnum):
    SET_IMPORTANT = "SET_IMPORTANT"
    SET_MY_DAY = "SET_MY_DAY"


@dataclass(frozen=True)
class TodoTaskFocus:
    task_key: str
    important: bool = False
    my_day: bool = False


@dataclass(frozen=True)
class TodoFocusRequest:
    action: TodoFocusAction
    task_key: str
    enabled: bool

    def __post_init__(self) -> None:
        if not isinstance(self.action, TodoFocusAction):
            raise ValueError("action must be a closed TodoFocusAction")
        _validate_key(self.task_key)
        if not isinstance(self.enabled, bool):
            raise ValueError("enabled must be boolean")


@dataclass(frozen=True)
class TodoFocusResult:
    action: TodoFocusAction
    task_key: str
    changed: bool
    read_back: TodoTaskFocus
    verified: bool
    synthetic: bool


def _validate_key(value: str) -> None:
    if not value or value != value.strip() or "@" in value or any(
        char.isspace() for char in value
    ):
        raise ValueError("task_key must be an opaque semantic token")


def _gate(fixture: OutlookMockFixture, readiness: OutlookReadinessReport) -> None:
    if not fixture.synthetic:
        raise ValueError("OUT-106 fixture execution requires synthetic=true")
    if not readiness.ready_for_readonly_discovery:
        raise ValueError("Outlook read-only discovery is not ready")


def _validate_focus(focus: tuple[TodoTaskFocus, ...]) -> None:
    keys = tuple(item.task_key for item in focus)
    if len(set(keys)) != len(keys):
        raise ValueError("focus task keys must be unique")
    for item in focus:
        _validate_key(item.task_key)


def apply_todo_focus(
    fixture: OutlookMockFixture,
    tasks: tuple[SyntheticTodoTask, ...],
    focus: tuple[TodoTaskFocus, ...],
    request: TodoFocusRequest,
    *,
    readiness: OutlookReadinessReport,
) -> tuple[tuple[TodoTaskFocus, ...], TodoFocusResult]:
    """Apply Important/My Day state locally with deterministic read-back."""
    _gate(fixture, readiness)
    _validate_focus(focus)
    task = next(
        (item for item in tasks if item.task_key == request.task_key),
        None,
    )
    if task is None:
        raise ValueError("synthetic task_key not found")
    existing = next(
        (item for item in focus if item.task_key == request.task_key),
        TodoTaskFocus(request.task_key),
    )
    if (
        request.action is TodoFocusAction.SET_MY_DAY
        and request.enabled
        and task.state is TaskState.COMPLETED
    ):
        raise ValueError("completed task cannot be added to My Day")

    if request.action is TodoFocusAction.SET_IMPORTANT:
        desired = TodoTaskFocus(
            request.task_key,
            important=request.enabled,
            my_day=existing.my_day,
        )
    elif request.action is TodoFocusAction.SET_MY_DAY:
        desired = TodoTaskFocus(
            request.task_key,
            important=existing.important,
            my_day=request.enabled,
        )
    else:
        raise ValueError("unsupported focus mutation")

    updated = tuple(
        item for item in focus if item.task_key != request.task_key
    ) + (desired,)
    updated = tuple(sorted(updated, key=lambda item: item.task_key))
    _validate_focus(updated)
    read_back = next(
        item for item in updated if item.task_key == request.task_key
    )
    if read_back != desired:
        raise RuntimeError("focus read-back did not prove requested state")
    return updated, TodoFocusResult(
        action=request.action,
        task_key=request.task_key,
        changed=desired != existing,
        read_back=read_back,
        verified=True,
        synthetic=True,
    )


__all__ = [
    "TodoFocusAction",
    "TodoFocusRequest",
    "TodoFocusResult",
    "TodoTaskFocus",
    "apply_todo_focus",
]
