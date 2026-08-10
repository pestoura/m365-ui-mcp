from m365_mcp.application_registry import ApplicationState
from m365_mcp.apps.outlook.calendar_events import (
    EventProjection,
    EventSensitivity,
    EventShowAs,
)
from m365_mcp.apps.outlook.manifest import foundation_manifest
from m365_mcp.apps.outlook.todo_task_reads import SyntheticTodoTask, TaskState
from m365_mcp.tool_registry import default_tool_registry
from m365_mcp.xapp_outlook_daily_work_context import build_synthetic_daily_work_context
from m365_mcp.xapp_outlook_inbox_digest import OutlookInboxDigest


def test_daily_work_context_reduces_synthetic_mail_calendar_and_todo() -> None:
    digest = OutlookInboxDigest(
        page_count=3,
        total_matching=3,
        unread_count=2,
        attachment_count=1,
        attention_message_keys=("msg-alpha", "msg-bravo"),
    )
    event = EventProjection(
        event_key="event-alpha",
        calendar_key="calendar-default",
        subject="Synthetic review",
        start_day_offset=0,
        start_minute_of_day=600,
        duration_minutes=30,
        end_day_offset=0,
        end_minute_of_day=630,
        is_all_day=False,
        is_cancelled=False,
        is_recurring_instance=False,
        show_as=EventShowAs.BUSY,
        sensitivity=EventSensitivity.NORMAL,
        synthetic=True,
    )
    tasks = (
        SyntheticTodoTask(
            "task-alpha",
            "todo-default",
            "Synthetic due task",
            TaskState.IN_PROGRESS,
            0,
        ),
        SyntheticTodoTask(
            "task-done",
            "todo-default",
            "Synthetic completed task",
            TaskState.COMPLETED,
            0,
        ),
    )

    context = build_synthetic_daily_work_context(digest, (event,), tasks)

    assert context.unread_mail_count == 2
    assert context.attachment_mail_count == 1
    assert context.event_keys == ("event-alpha",)
    assert context.open_task_keys == ("task-alpha",)
    assert context.synthetic is True
    assert context.live_observed is False
    assert context.execution_performed is False


def test_outlook_boundary_remains_reserved_and_private() -> None:
    assert foundation_manifest().state is ApplicationState.RESERVED
    assert default_tool_registry().by_application("outlook") == ()
