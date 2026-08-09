from __future__ import annotations

import pytest

from m365_mcp.application_registry import (
    ApplicationKey,
    ApplicationState,
    default_application_registry,
)
from m365_mcp.apps.outlook import (
    mock_ui,
    readiness,
    todo_task_focus,
    todo_task_reads,
)
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


def test_important_and_my_day_preserve_each_other_with_read_back() -> None:
    fixture = mock_ui.default_outlook_fixture()
    _, tasks = todo_task_reads.default_synthetic_todo()
    focus, important = todo_task_focus.apply_todo_focus(
        fixture,
        tasks,
        (),
        todo_task_focus.TodoFocusRequest(
            todo_task_focus.TodoFocusAction.SET_IMPORTANT,
            "task-alpha",
            True,
        ),
        readiness=_ready(),
    )
    assert important.read_back.important is True
    focus, my_day = todo_task_focus.apply_todo_focus(
        fixture,
        tasks,
        focus,
        todo_task_focus.TodoFocusRequest(
            todo_task_focus.TodoFocusAction.SET_MY_DAY,
            "task-alpha",
            True,
        ),
        readiness=_ready(),
    )
    assert my_day.read_back.important is True
    assert my_day.read_back.my_day is True


def test_focus_mutation_is_idempotent() -> None:
    fixture = mock_ui.default_outlook_fixture()
    _, tasks = todo_task_reads.default_synthetic_todo()
    focus = (todo_task_focus.TodoTaskFocus("task-bravo", important=True),)
    _, result = todo_task_focus.apply_todo_focus(
        fixture,
        tasks,
        focus,
        todo_task_focus.TodoFocusRequest(
            todo_task_focus.TodoFocusAction.SET_IMPORTANT,
            "task-bravo",
            True,
        ),
        readiness=_ready(),
    )
    assert result.changed is False


def test_my_day_rejects_completed_or_unknown_task() -> None:
    fixture = mock_ui.default_outlook_fixture()
    _, tasks = todo_task_reads.default_synthetic_todo()
    with pytest.raises(ValueError, match="completed task"):
        todo_task_focus.apply_todo_focus(
            fixture,
            tasks,
            (),
            todo_task_focus.TodoFocusRequest(
                todo_task_focus.TodoFocusAction.SET_MY_DAY,
                "task-charlie",
                True,
            ),
            readiness=_ready(),
        )
    with pytest.raises(ValueError, match="task_key not found"):
        todo_task_focus.apply_todo_focus(
            fixture,
            tasks,
            (),
            todo_task_focus.TodoFocusRequest(
                todo_task_focus.TodoFocusAction.SET_IMPORTANT,
                "task-missing",
                True,
            ),
            readiness=_ready(),
        )


def test_out106_remains_reserved_and_not_public() -> None:
    outlook = default_application_registry().get(ApplicationKey.OUTLOOK)
    assert outlook.state is ApplicationState.RESERVED
    assert default_tool_registry().by_application("outlook") == ()
