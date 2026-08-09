from __future__ import annotations

import pytest

from m365_mcp.application_registry import (
    ApplicationKey,
    ApplicationState,
    default_application_registry,
)
from m365_mcp.apps.outlook import (
    follow_up_reads,
    mock_ui,
    readiness,
    todo_flagged_email_relationship,
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


def test_flagged_message_link_and_unlink_have_exact_read_back() -> None:
    fixture = mock_ui.default_outlook_fixture()
    _, tasks = todo_task_reads.default_synthetic_todo()
    links, linked = (
        todo_flagged_email_relationship.apply_flagged_email_task_relationship(
            fixture,
            tasks,
            (),
            todo_flagged_email_relationship.FlaggedEmailTaskRequest(
                todo_flagged_email_relationship.FlaggedEmailTaskAction.LINK,
                "msg-001",
                "task-alpha",
            ),
            readiness=_ready(),
        )
    )
    assert linked.read_back is not None
    assert linked.read_back.task_key == "task-alpha"
    links, unlinked = (
        todo_flagged_email_relationship.apply_flagged_email_task_relationship(
            fixture,
            tasks,
            links,
            todo_flagged_email_relationship.FlaggedEmailTaskRequest(
                todo_flagged_email_relationship.FlaggedEmailTaskAction.UNLINK,
                "msg-001",
                "task-alpha",
            ),
            readiness=_ready(),
        )
    )
    assert links == ()
    assert unlinked.read_back is None


def test_flagged_message_link_is_idempotent() -> None:
    fixture = mock_ui.default_outlook_fixture()
    _, tasks = todo_task_reads.default_synthetic_todo()
    link = todo_flagged_email_relationship.FlaggedEmailTaskLink(
        "msg-001",
        "task-alpha",
    )
    _, repeated = (
        todo_flagged_email_relationship.apply_flagged_email_task_relationship(
            fixture,
            tasks,
            (link,),
            todo_flagged_email_relationship.FlaggedEmailTaskRequest(
                todo_flagged_email_relationship.FlaggedEmailTaskAction.LINK,
                "msg-001",
                "task-alpha",
            ),
            readiness=_ready(),
        )
    )
    assert repeated.changed is False


def test_relationship_requires_currently_flagged_message_and_known_task() -> None:
    fixture = mock_ui.default_outlook_fixture()
    _, tasks = todo_task_reads.default_synthetic_todo()
    flags = (
        follow_up_reads.FollowUpFlag(
            "msg-001",
            follow_up_reads.FollowUpState.NOT_FLAGGED,
        ),
    )
    with pytest.raises(ValueError, match="flagged follow-up state"):
        todo_flagged_email_relationship.apply_flagged_email_task_relationship(
            fixture,
            tasks,
            (),
            todo_flagged_email_relationship.FlaggedEmailTaskRequest(
                todo_flagged_email_relationship.FlaggedEmailTaskAction.LINK,
                "msg-001",
                "task-alpha",
            ),
            readiness=_ready(),
            flags=flags,
        )
    with pytest.raises(ValueError, match="task_key not found"):
        todo_flagged_email_relationship.apply_flagged_email_task_relationship(
            fixture,
            tasks,
            (),
            todo_flagged_email_relationship.FlaggedEmailTaskRequest(
                todo_flagged_email_relationship.FlaggedEmailTaskAction.LINK,
                "msg-001",
                "task-missing",
            ),
            readiness=_ready(),
        )


def test_out109_remains_reserved_and_not_public() -> None:
    outlook = default_application_registry().get(ApplicationKey.OUTLOOK)
    assert outlook.state is ApplicationState.RESERVED
    assert default_tool_registry().by_application("outlook") == ()
