from __future__ import annotations

import pytest

from m365_mcp.application_registry import (
    ApplicationKey,
    ApplicationState,
    default_application_registry,
)
from m365_mcp.apps.outlook import organizer_response_tracking, readiness
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


def _records() -> tuple[
    organizer_response_tracking.SyntheticOrganizerResponseRecord, ...
]:
    record = organizer_response_tracking.SyntheticOrganizerResponseRecord
    response = organizer_response_tracking.TrackedMeetingResponse
    return (
        record("meeting-001", "person-charlie", response.DECLINED),
        record("meeting-001", "person-alpha", response.ACCEPTED),
        record("meeting-001", "person-bravo", response.TENTATIVE),
        record("meeting-002", "person-delta", response.NONE),
    )


def test_response_tracking_lists_deterministically_and_summarizes() -> None:
    selected = organizer_response_tracking.list_organizer_responses(
        _records(),
        meeting_key="meeting-001",
        readiness=_ready(),
    )
    assert tuple(item.participant_key for item in selected) == (
        "person-alpha",
        "person-bravo",
        "person-charlie",
    )
    summary = organizer_response_tracking.summarize_organizer_responses(
        _records(),
        meeting_key="meeting-001",
        readiness=_ready(),
    )
    assert summary.total == 3
    assert summary.accepted == 1
    assert summary.tentative == 1
    assert summary.declined == 1
    assert summary.none == 0


def test_response_tracking_rejects_email_shape_and_duplicates() -> None:
    with pytest.raises(ValueError, match="email address"):
        organizer_response_tracking.SyntheticOrganizerResponseRecord(
            "meeting-001",
            "someone@example.invalid",
            organizer_response_tracking.TrackedMeetingResponse.NONE,
        )

    duplicate = _records() + (_records()[0],)
    with pytest.raises(ValueError, match="duplicate participant identity"):
        organizer_response_tracking.list_organizer_responses(
            duplicate,
            meeting_key="meeting-001",
            readiness=_ready(),
        )


def test_out091_remains_reserved_and_not_public() -> None:
    outlook = default_application_registry().get(ApplicationKey.OUTLOOK)
    assert outlook.state is ApplicationState.RESERVED
    assert default_tool_registry().by_application("outlook") == ()
