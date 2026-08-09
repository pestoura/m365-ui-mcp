from __future__ import annotations

import pytest

from m365_mcp.application_registry import (
    ApplicationKey,
    ApplicationState,
    default_application_registry,
)
from m365_mcp.apps.outlook import mock_ui, readiness, todo_task_reads
from m365_mcp.apps.outlook import todo_task_schedule
from m365_mcp.tool_registry import default_tool_registry


def _ready() -> readiness.OutlookReadinessReport:
    return readiness.OutlookReadinessReport(
        state=readiness.OutlookReadinessState.DISCOVERY_READY,
        primary_context_verified=True,
        shared_context_verified=False,
        candidate_count=1,
        observed_count=1,
        blocked_count=0,
        reattestation_count=0,
    )


def test_schedule_set_and_clear_update_task_due_date_with_read_back() -> None:
    fixture = mock_ui.default_outlook_fixture()
    _, tasks = todo_task_reads.default_synthetic_todo()
    tasks, schedules, result = todo_task_schedule.apply_todo_schedule(
        fixture,
        tasks,
        (),
        todo_task_schedule.TodoScheduleRequest(
            todo_task_schedule.TodoScheduleAction.SET,
            "task-alpha",
            due_day_offset=7,
            reminder_day_offset=6,
            recurrence=todo_task_schedule.TodoRecurrenceKind.WEEKLY,
            recurrence_interval=2,
        ),
        readiness=_ready(),
    )
    assert result.read_back is not None
    assert result.read_back.recurrence_interval == 2
    task = next(item for item in tasks if item.task_key == "task-alpha")
    assert task.due_day_offset == 7
    tasks, schedules, cleared = todo_task_schedule.apply_todo_schedule(
        fixture,
        tasks,
        schedules,
        todo_task_schedule.TodoScheduleRequest(
            todo_task_schedule.TodoScheduleAction.CLEAR,
            "task-alpha",
        ),
        readiness=_ready(),
    )
    assert schedules == ()
    assert cleared.read_back is None
    task = next(item for item in tasks if item.task_key == "task-alpha")
    assert task.due_day_offset is None


def test_schedule_set_is_idempotent() -> None:
    fixture = mock_ui.default_outlook_fixture()
    _, tasks = todo_task_reads.default_synthetic_todo()
    request = todo_task_schedule.TodoScheduleRequest(
        todo_task_schedule.TodoScheduleAction.SET,
        "task-bravo",
        due_day_offset=4,
    )
    tasks, schedules, first = todo_task_schedule.apply_todo_schedule(
        fixture,
        tasks,
        (),
        request,
        readiness=_ready(),
    )
    _, _, second = todo_task_schedule.apply_todo_schedule(
        fixture,
        tasks,
        schedules,
        request,
        readiness=_ready(),
    )
    assert first.changed is True
    assert second.changed is False


def test_schedule_fails_closed_on_invalid_reminder_and_unknown_task() -> None:
    with pytest.raises(ValueError, match="must not be after"):
        todo_task_schedule.TodoScheduleRequest(
            todo_task_schedule.TodoScheduleAction.SET,
            "task-alpha",
            due_day_offset=2,
            reminder_day_offset=3,
        )
    fixture = mock_ui.default_outlook_fixture()
    _, tasks = todo_task_reads.default_synthetic_todo()
    with pytest.raises(ValueError, match="task_key not found"):
        todo_task_schedule.apply_todo_schedule(
            fixture,
            tasks,
            (),
            todo_task_schedule.TodoScheduleRequest(
                todo_task_schedule.TodoScheduleAction.CLEAR,
                "task-missing",
            ),
            readiness=_ready(),
        )


def test_out105_remains_reserved_and_not_public() -> None:
    outlook = default_application_registry().get(ApplicationKey.OUTLOOK)
    assert outlook.state is ApplicationState.RESERVED
    assert default_tool_registry().by_application("outlook") == ()
