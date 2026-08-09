"""Synthetic-only Outlook To Do list/task reads for OUT-028."""
from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from m365_mcp.apps.outlook.mock_ui import OutlookMockFixture
from m365_mcp.apps.outlook.readiness import OutlookReadinessReport

_MAX_LISTS = 50
_MAX_TASKS = 500


class TaskState(StrEnum):
    NOT_STARTED = "NOT_STARTED"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"


@dataclass(frozen=True)
class SyntheticTodoList:
    list_key: str
    display_name: str

    def __post_init__(self) -> None:
        invalid_list_key = (
            not self.list_key
            or self.list_key != self.list_key.strip()
            or "@" in self.list_key
        )
        if invalid_list_key:
            raise ValueError("list_key must be opaque")


@dataclass(frozen=True)
class SyntheticTodoTask:
    task_key: str
    list_key: str
    title: str
    state: TaskState = TaskState.NOT_STARTED
    due_day_offset: int | None = None

    def __post_init__(self) -> None:
        invalid_task_key = (
            not self.task_key
            or self.task_key != self.task_key.strip()
            or "@" in self.task_key
        )
        if invalid_task_key:
            raise ValueError("task_key must be opaque")
        if not self.title or self.title != self.title.strip():
            raise ValueError("title must be non-empty and trimmed")
        if not isinstance(self.state, TaskState):
            raise ValueError("state must be a closed TaskState")
        invalid_due_offset = self.due_day_offset is not None and (
            isinstance(self.due_day_offset, bool)
            or not -3650 <= self.due_day_offset <= 3650
        )
        if invalid_due_offset:
            raise ValueError("due_day_offset must be bounded")

    def to_projection(self) -> dict[str, object]:
        return {
            "task_key": self.task_key,
            "list_key": self.list_key,
            "title": self.title,
            "state": self.state.value,
            "due_day_offset": self.due_day_offset,
            "synthetic": True,
        }


def default_synthetic_todo(
) -> tuple[tuple[SyntheticTodoList, ...], tuple[SyntheticTodoTask, ...]]:
    lists = (
        SyntheticTodoList("todo-default", "Tasks"),
        SyntheticTodoList("todo-project", "Project"),
    )
    tasks = (
        SyntheticTodoTask(
            "task-alpha",
            "todo-default",
            "Review synthetic item",
            TaskState.IN_PROGRESS,
            1,
        ),
        SyntheticTodoTask(
            "task-bravo",
            "todo-project",
            "Prepare synthetic note",
            TaskState.NOT_STARTED,
            3,
        ),
        SyntheticTodoTask(
            "task-charlie",
            "todo-default",
            "Closed synthetic task",
            TaskState.COMPLETED,
            -1,
        ),
    )
    return lists, tasks


def _gate(fixture: OutlookMockFixture, readiness: OutlookReadinessReport) -> None:
    if not fixture.synthetic:
        raise ValueError("OUT-028 fixture execution requires synthetic=true")
    if not readiness.ready_for_readonly_discovery:
        raise ValueError("Outlook read-only discovery is not ready")


def _validate(
    lists: tuple[SyntheticTodoList, ...],
    tasks: tuple[SyntheticTodoTask, ...],
) -> None:
    if not lists or len(lists) > _MAX_LISTS or len(tasks) > _MAX_TASKS:
        raise ValueError("To Do catalog must be bounded")
    list_keys = {item.list_key for item in lists}
    if len(list_keys) != len(lists):
        raise ValueError("To Do list keys must be unique")
    task_keys = {item.task_key for item in tasks}
    if len(task_keys) != len(tasks):
        raise ValueError("To Do task keys must be unique")
    if any(item.list_key not in list_keys for item in tasks):
        raise ValueError("task list_key must reference a synthetic To Do list")


def read_fixture_todo(
    fixture: OutlookMockFixture,
    *,
    readiness: OutlookReadinessReport,
    lists: tuple[SyntheticTodoList, ...] | None = None,
    tasks: tuple[SyntheticTodoTask, ...] | None = None,
) -> dict[str, object]:
    _gate(fixture, readiness)
    default_lists, default_tasks = default_synthetic_todo()
    use_lists = default_lists if lists is None else lists
    use_tasks = default_tasks if tasks is None else tasks
    _validate(use_lists, use_tasks)
    list_projection = tuple(
        {"list_key": item.list_key, "display_name": item.display_name}
        for item in use_lists
    )
    return {
        "lists": list_projection,
        "tasks": tuple(item.to_projection() for item in use_tasks),
        "synthetic": True,
    }


def list_fixture_tasks(
    fixture: OutlookMockFixture,
    list_key: str,
    *,
    readiness: OutlookReadinessReport,
    lists: tuple[SyntheticTodoList, ...] | None = None,
    tasks: tuple[SyntheticTodoTask, ...] | None = None,
) -> tuple[SyntheticTodoTask, ...]:
    data = read_fixture_todo(fixture, readiness=readiness, lists=lists, tasks=tasks)
    available = {item["list_key"] for item in data["lists"]}  # type: ignore[index]
    if list_key not in available:
        raise ValueError("synthetic To Do list_key not found")
    source = default_synthetic_todo()[1] if tasks is None else tasks
    return tuple(item for item in source if item.list_key == list_key)


__all__ = [
    "SyntheticTodoList",
    "SyntheticTodoTask",
    "TaskState",
    "default_synthetic_todo",
    "list_fixture_tasks",
    "read_fixture_todo",
]
