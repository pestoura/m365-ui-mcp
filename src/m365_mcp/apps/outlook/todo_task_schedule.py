"""Synthetic-only Outlook To Do scheduling mutations for OUT-105.

Due dates, reminders and recurrence are represented as bounded relative semantic
values. No tenant time zone, URL, selector, token, session or live mailbox
material is accepted or produced.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from m365_mcp.apps.outlook.mock_ui import OutlookMockFixture
from m365_mcp.apps.outlook.readiness import OutlookReadinessReport
from m365_mcp.apps.outlook.todo_task_reads import SyntheticTodoTask

_MAX_DAY_OFFSET = 3650
_MAX_RECURRENCE_INTERVAL = 365


class TodoRecurrenceKind(StrEnum):
    NONE = "NONE"
    DAILY = "DAILY"
    WEEKLY = "WEEKLY"
    MONTHLY = "MONTHLY"


class TodoScheduleAction(StrEnum):
    SET = "SET"
    CLEAR = "CLEAR"


@dataclass(frozen=True)
class TodoTaskSchedule:
    task_key: str
    due_day_offset: int | None
    reminder_day_offset: int | None
    recurrence: TodoRecurrenceKind
    recurrence_interval: int

    def __post_init__(self) -> None:
        _validate_key(self.task_key)
        _validate_day("due_day_offset", self.due_day_offset)
        _validate_day("reminder_day_offset", self.reminder_day_offset)
        if (
            self.due_day_offset is not None
            and self.reminder_day_offset is not None
            and self.reminder_day_offset > self.due_day_offset
        ):
            raise ValueError("reminder_day_offset must not be after due_day_offset")
        if not isinstance(self.recurrence, TodoRecurrenceKind):
            raise ValueError("recurrence must be a closed TodoRecurrenceKind")
        if self.recurrence is TodoRecurrenceKind.NONE:
            if self.recurrence_interval != 1:
                raise ValueError("NONE recurrence requires interval=1")
        elif not 1 <= self.recurrence_interval <= _MAX_RECURRENCE_INTERVAL:
            raise ValueError("recurrence_interval outside bounded range")


@dataclass(frozen=True)
class TodoScheduleRequest:
    action: TodoScheduleAction
    task_key: str
    due_day_offset: int | None = None
    reminder_day_offset: int | None = None
    recurrence: TodoRecurrenceKind = TodoRecurrenceKind.NONE
    recurrence_interval: int = 1

    def __post_init__(self) -> None:
        if not isinstance(self.action, TodoScheduleAction):
            raise ValueError("action must be a closed TodoScheduleAction")
        _validate_key(self.task_key)
        if self.action is TodoScheduleAction.SET:
            TodoTaskSchedule(
                self.task_key,
                self.due_day_offset,
                self.reminder_day_offset,
                self.recurrence,
                self.recurrence_interval,
            )


@dataclass(frozen=True)
class TodoScheduleResult:
    action: TodoScheduleAction
    task_key: str
    changed: bool
    read_back: TodoTaskSchedule | None
    verified: bool
    synthetic: bool


def _validate_key(value: str) -> None:
    if not value or value != value.strip() or "@" in value or any(
        char.isspace() for char in value
    ):
        raise ValueError("task_key must be an opaque semantic token")


def _validate_day(name: str, value: int | None) -> None:
    if value is not None and not -_MAX_DAY_OFFSET <= value <= _MAX_DAY_OFFSET:
        raise ValueError(f"{name} outside bounded range")


def _gate(fixture: OutlookMockFixture, readiness: OutlookReadinessReport) -> None:
    if not fixture.synthetic:
        raise ValueError("OUT-105 fixture execution requires synthetic=true")
    if not readiness.ready_for_readonly_discovery:
        raise ValueError("Outlook read-only discovery is not ready")


def _validate_schedules(schedules: tuple[TodoTaskSchedule, ...]) -> None:
    keys = tuple(item.task_key for item in schedules)
    if len(set(keys)) != len(keys):
        raise ValueError("schedule task keys must be unique")


def apply_todo_schedule(
    fixture: OutlookMockFixture,
    tasks: tuple[SyntheticTodoTask, ...],
    schedules: tuple[TodoTaskSchedule, ...],
    request: TodoScheduleRequest,
    *,
    readiness: OutlookReadinessReport,
) -> tuple[
    tuple[SyntheticTodoTask, ...],
    tuple[TodoTaskSchedule, ...],
    TodoScheduleResult,
]:
    """Apply one synthetic scheduling mutation with exact read-back."""
    _gate(fixture, readiness)
    _validate_schedules(schedules)
    task = next(
        (item for item in tasks if item.task_key == request.task_key),
        None,
    )
    if task is None:
        raise ValueError("synthetic task_key not found")
    existing = next(
        (item for item in schedules if item.task_key == request.task_key),
        None,
    )

    if request.action is TodoScheduleAction.SET:
        desired = TodoTaskSchedule(
            request.task_key,
            request.due_day_offset,
            request.reminder_day_offset,
            request.recurrence,
            request.recurrence_interval,
        )
        updated_schedules = tuple(
            item for item in schedules if item.task_key != request.task_key
        ) + (desired,)
        desired_task = SyntheticTodoTask(
            task.task_key,
            task.list_key,
            task.title,
            task.state,
            request.due_day_offset,
        )
        expected: TodoTaskSchedule | None = desired
    elif request.action is TodoScheduleAction.CLEAR:
        updated_schedules = tuple(
            item for item in schedules if item.task_key != request.task_key
        )
        desired_task = SyntheticTodoTask(
            task.task_key,
            task.list_key,
            task.title,
            task.state,
            None,
        )
        expected = None
    else:
        raise ValueError("unsupported schedule mutation")

    updated_tasks = tuple(
        desired_task if item.task_key == request.task_key else item for item in tasks
    )
    updated_schedules = tuple(
        sorted(updated_schedules, key=lambda item: item.task_key)
    )
    _validate_schedules(updated_schedules)
    read_back = next(
        (item for item in updated_schedules if item.task_key == request.task_key),
        None,
    )
    if read_back != expected:
        raise RuntimeError("schedule read-back did not prove requested state")
    changed = existing != expected or desired_task != task
    return updated_tasks, updated_schedules, TodoScheduleResult(
        action=request.action,
        task_key=request.task_key,
        changed=changed,
        read_back=read_back,
        verified=True,
        synthetic=True,
    )


__all__ = [
    "TodoRecurrenceKind",
    "TodoScheduleAction",
    "TodoScheduleRequest",
    "TodoScheduleResult",
    "TodoTaskSchedule",
    "apply_todo_schedule",
]
