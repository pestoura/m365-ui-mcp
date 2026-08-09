from __future__ import annotations

import pytest

from m365_mcp.application_registry import (
    ApplicationKey,
    ApplicationState,
    default_application_registry,
)
from m365_mcp.apps.outlook import meeting_responses, readiness
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


def test_response_requires_prepare_allowance_and_never_sends() -> None:
    desired = meeting_responses.SyntheticMeetingResponse(
        meeting_key="meeting-001",
        response=meeting_responses.MeetingResponseKind.ACCEPT,
    )
    with pytest.raises(PermissionError, match="outbound-prepare"):
        meeting_responses.prepare_meeting_response((), desired, readiness=_ready())

    responses, result = meeting_responses.prepare_meeting_response(
        (),
        desired,
        readiness=_ready(),
        allow_outbound_prepare=True,
    )
    assert responses == (desired,)
    assert result.response_sent is False
    assert result.verified is True
    assert (
        result.disposition
        is meeting_responses.MeetingResponseDisposition.PREPARED_NOT_SENT
    )


def test_response_update_is_idempotent() -> None:
    desired = meeting_responses.SyntheticMeetingResponse(
        meeting_key="meeting-001",
        response=meeting_responses.MeetingResponseKind.TENTATIVE,
    )
    responses, _ = meeting_responses.prepare_meeting_response(
        (), desired, readiness=_ready(), allow_outbound_prepare=True
    )
    responses, result = meeting_responses.prepare_meeting_response(
        responses,
        desired,
        readiness=_ready(),
        allow_outbound_prepare=True,
    )
    assert result.changed is False
    assert responses == (desired,)


def test_out086_remains_reserved_and_not_public() -> None:
    outlook = default_application_registry().get(ApplicationKey.OUTLOOK)
    assert outlook.state is ApplicationState.RESERVED
    assert default_tool_registry().by_application("outlook") == ()
