"""Synthetic-only Outlook To Do task-step mutations for OUT-107."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from m365_mcp.apps.outlook.mock_ui import OutlookMockFixture
from m365_mcp.apps.outlook.readiness import OutlookReadinessReport
from m365_mcp.apps.outlook.todo_task_reads import SyntheticTodoTask

_MAX_STEPS_PER_TASK = 100


class TodoStepAction(StrEnum):
    ADD = "ADD"
    UPDATE = "UPDATE"
    COMPLETE = "COMPLETE"
    DELETE = "DELETE"


def _validate_key(name: str, value: str) -> None:
    if not value or value != value.strip() or "@" in value or any(
        char.isspace() for char in value
    ):
        raise ValueError(f"{name} must be an opaque semantic token")


@dataclass(frozen=True)
class SyntheticTodoStep:
    step_key: str
    task_key: str
    title: str
    completed: bool = False

    def __post_init__(self) -> None:
        _validate_key("step_key", self.step_key)
        _validate_key("task_key", self.task_key)
        if not self.title or self.title != self.title.strip():
            raise ValueError("title must be non-empty and trimmed")
        if not isinstance(self.completed, bool):
            raise ValueError("completed must be boolean")


@dataclass(frozen=True)
class TodoStepRequest:
    action: TodoStepAction
    task_key: str
    step_key: str
    title: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.action, TodoStepAction):
            raise ValueError("action must be a closed TodoStepAction")
        _validate_key("task_key", self.task_key)
        _validate_key("step_key", self.step_key)
        if self.action in (TodoStepAction.ADD, TodoStepAction.UPDATE):
            if not self.title or self.title != self.title.strip():
                raise ValueError("add/update requires a non-empty trimmed title")


@dataclass(frozen=True)
class TodoStepResult:
    action: TodoStepAction
    task_key: str
    step_key: str
    changed: bool
    read_back: SyntheticTodoStep | None
    verified: bool
    synthetic: bool


def _gate(fixture: OutlookMockFixture, readiness: OutlookReadinessReport) -> None:
    if not fixture.synthetic:
        raise ValueError("OUT-107 fixture execution requires synthetic=true")
    if not readiness.ready_for_readonly_discovery:
        raise ValueError("Outlook read-only discovery is not ready")


def _validate_steps(steps: tuple[SyntheticTodoStep, ...]) -> None:
    keys = tuple(item.step_key for item in steps)
    if len(set(keys)) != len(keys):
        raise ValueError("step keys must be unique")
    counts: dict[str, int] = {}
    for item in steps:
        counts[item.task_key] = counts.get(item.task_key, 0) + 1
        if counts[item.task_key] > _MAX_STEPS_PER_TASK:
            raise ValueError("task step count exceeds bounded size")


def apply_todo_step(
    fixture: OutlookMockFixture,
    tasks: tuple[SyntheticTodoTask, ...],
    steps: tuple[SyntheticTodoStep, ...],
    request: TodoStepRequest,
    *,
    readiness: OutlookReadinessReport,
) -> tuple[tuple[SyntheticTodoStep, ...], TodoStepResult]:
    """Apply one bounded task-step mutation and prove exact local read-back."""
    _gate(fixture, readiness)
    _validate_steps(steps)
    if not any(item.task_key == request.task_key for item in tasks):
        raise ValueError("synthetic task_key not found")

    existing = next(
        (item for item in steps if item.step_key == request.step_key),
        None,
    )
    if existing is not None and existing.task_key != request.task_key:
        raise ValueError("step_key belongs to a different synthetic task")

    if request.action is TodoStepAction.ADD:
        desired = SyntheticTodoStep(
            request.step_key,
            request.task_key,
            request.title or "",
        )
        if existing is None:
            count = sum(1 for item in steps if item.task_key == request.task_key)
            if count >= _MAX_STEPS_PER_TASK:
                raise ValueError("task step count exceeds bounded size")
            updated = steps + (desired,)
            changed = True
        elif existing == desired:
            updated = steps
            changed = False
        else:
            raise ValueError("step_key already exists with different state")
        expected: SyntheticTodoStep | None = desired
    elif request.action is TodoStepAction.UPDATE:
        if existing is None:
            raise ValueError("synthetic step_key not found")
        desired = SyntheticTodoStep(
            existing.step_key,
            existing.task_key,
            request.title or "",
            existing.completed,
        )
        updated = tuple(
            desired if item.step_key == request.step_key else item for item in steps
        )
        changed = desired != existing
        expected = desired
    elif request.action is TodoStepAction.COMPLETE:
        if existing is None:
            raise ValueError("synthetic step_key not found")
        desired = SyntheticTodoStep(
            existing.step_key,
            existing.task_key,
            existing.title,
            True,
        )
        updated = tuple(
            desired if item.step_key == request.step_key else item for item in steps
        )
        changed = desired != existing
        expected = desired
    elif request.action is TodoStepAction.DELETE:
        updated = tuple(item for item in steps if item.step_key != request.step_key)
        changed = existing is not None
        expected = None
    else:
        raise ValueError("unsupported step mutation")

    updated = tuple(sorted(updated, key=lambda item: item.step_key))
    _validate_steps(updated)
    read_back = next(
        (item for item in updated if item.step_key == request.step_key),
        None,
    )
    if read_back != expected:
        raise RuntimeError("step read-back did not prove requested state")
    return updated, TodoStepResult(
        action=request.action,
        task_key=request.task_key,
        step_key=request.step_key,
        changed=changed,
        read_back=read_back,
        verified=True,
        synthetic=True,
    )


__all__ = [
    "SyntheticTodoStep",
    "TodoStepAction",
    "TodoStepRequest",
    "TodoStepResult",
    "apply_todo_step",
]
