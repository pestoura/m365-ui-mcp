from __future__ import annotations

import pytest

from m365_mcp.application_registry import (
    ApplicationKey,
    ApplicationState,
    default_application_registry,
)
from m365_mcp.apps.outlook import meeting_response_messages, readiness
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


def test_response_message_requires_prepare_allowance_and_never_sends() -> None:
    desired = meeting_response_messages.SyntheticMeetingResponseMessage(
        meeting_key="meeting-001",
        response=meeting_response_messages.MeetingResponseMessageKind.DECLINE,
        message_text="Synthetic decline context",
    )
    with pytest.raises(PermissionError, match="outbound-prepare"):
        meeting_response_messages.prepare_response_with_message(
            (), desired, readiness=_ready()
        )

    messages, result = meeting_response_messages.prepare_response_with_message(
        (),
        desired,
        readiness=_ready(),
        allow_outbound_prepare=True,
    )
    assert messages == (desired,)
    assert result.response_sent is False
    assert result.verified is True


def test_response_message_rejects_nul_and_is_idempotent() -> None:
    with pytest.raises(ValueError, match="NUL"):
        meeting_response_messages.SyntheticMeetingResponseMessage(
            meeting_key="meeting-001",
            response=meeting_response_messages.MeetingResponseMessageKind.ACCEPT,
            message_text="bad\x00message",
        )

    desired = meeting_response_messages.SyntheticMeetingResponseMessage(
        meeting_key="meeting-001",
        response=meeting_response_messages.MeetingResponseMessageKind.ACCEPT,
        message_text="Synthetic response",
    )
    messages, _ = meeting_response_messages.prepare_response_with_message(
        (), desired, readiness=_ready(), allow_outbound_prepare=True
    )
    messages, result = meeting_response_messages.prepare_response_with_message(
        messages,
        desired,
        readiness=_ready(),
        allow_outbound_prepare=True,
    )
    assert result.changed is False
    assert messages == (desired,)


def test_out087_remains_reserved_and_not_public() -> None:
    outlook = default_application_registry().get(ApplicationKey.OUTLOOK)
    assert outlook.state is ApplicationState.RESERVED
    assert default_tool_registry().by_application("outlook") == ()
