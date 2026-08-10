from __future__ import annotations

from m365_mcp.application_registry import (
    ApplicationKey,
    ApplicationState,
    default_application_registry,
)
from m365_mcp.apps.outlook import email_poll_management, readiness
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


def test_email_poll_create_manage_vote_close_and_results() -> None:
    polls, created = email_poll_management.apply_email_poll_action(
        (),
        action=email_poll_management.EmailPollAction.CREATE,
        poll_key="poll-email-001",
        question="Choose a synthetic option",
        readiness=_ready(),
    )
    assert created.state is email_poll_management.EmailPollState.PREPARED

    option = email_poll_management.EmailPollOption("option-alpha", "Alpha")
    polls, added = email_poll_management.apply_email_poll_action(
        polls,
        action=email_poll_management.EmailPollAction.ADD_OPTION,
        poll_key="poll-email-001",
        option=option,
        readiness=_ready(),
    )
    assert added.tallies == (("option-alpha", 0),)

    polls, voted = email_poll_management.apply_email_poll_action(
        polls,
        action=email_poll_management.EmailPollAction.RECORD_VOTE,
        poll_key="poll-email-001",
        option_key="option-alpha",
        participant_key="participant-001",
        readiness=_ready(),
    )
    assert voted.total_votes == 1
    assert polls[0].dispatched is False

    _, closed = email_poll_management.apply_email_poll_action(
        polls,
        action=email_poll_management.EmailPollAction.CLOSE,
        poll_key="poll-email-001",
        readiness=_ready(),
    )
    assert closed.state is email_poll_management.EmailPollState.CLOSED


def test_out136_remains_reserved_and_not_public() -> None:
    outlook = default_application_registry().get(ApplicationKey.OUTLOOK)
    assert outlook.state is ApplicationState.RESERVED
    assert default_tool_registry().by_application("outlook") == ()
