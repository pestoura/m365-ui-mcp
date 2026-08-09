from __future__ import annotations

from m365_mcp.application_registry import (
    ApplicationKey,
    ApplicationState,
    default_application_registry,
)
from m365_mcp.apps.outlook import email_to_todo, mock_ui, readiness, todo_task_reads
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


def test_email_to_task_projects_subject_and_is_idempotent() -> None:
    fixture = mock_ui.default_outlook_fixture()
    lists, tasks = todo_task_reads.default_synthetic_todo()
    request = email_to_todo.EmailToTodoRequest(
        "msg-001",
        "task-from-msg-001",
        "todo-default",
    )
    tasks, first = email_to_todo.create_todo_from_email(
        fixture,
        lists,
        tasks,
        request,
        readiness=_ready(),
    )
    created = next(item for item in tasks if item.task_key == request.task_key)
    source = next(item for item in fixture.messages if item.message_key == "msg-001")
    assert created.title == source.subject
    _, repeated = email_to_todo.create_todo_from_email(
        fixture,
        lists,
        tasks,
        request,
        readiness=_ready(),
    )
    assert first.task_result.changed is True
    assert repeated.task_result.changed is False


def test_email_to_task_preserves_outlook_reservation() -> None:
    outlook = default_application_registry().get(ApplicationKey.OUTLOOK)
    assert outlook.state is ApplicationState.RESERVED
    assert default_tool_registry().by_application("outlook") == ()
