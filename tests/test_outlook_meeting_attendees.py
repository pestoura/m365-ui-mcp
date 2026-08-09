from __future__ import annotations

import pytest

from m365_mcp.application_registry import (
    ApplicationKey,
    ApplicationState,
    default_application_registry,
)
from m365_mcp.apps.outlook import meeting_attendees, readiness, recipient_resolution
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


def _candidates() -> tuple[recipient_resolution.SyntheticRecipientCandidate, ...]:
    return (
        recipient_resolution.SyntheticRecipientCandidate(
            recipient_key="person-alpha",
            aliases=("alpha",),
        ),
        recipient_resolution.SyntheticRecipientCandidate(
            recipient_key="room-blue",
            aliases=("blue-room",),
        ),
    )


def test_attendee_upsert_requires_prepare_allowance_and_never_sends() -> None:
    request = meeting_attendees.AttendeeMutationRequest(
        meeting_attendees.AttendeeMutationAction.UPSERT,
        meeting_key="meeting-001",
        participant_key="person-alpha",
        role=meeting_attendees.AttendeeRole.REQUIRED,
    )
    with pytest.raises(PermissionError, match="outbound-prepare"):
        meeting_attendees.mutate_meeting_attendees(
            (),
            request,
            readiness=_ready(),
            candidates=_candidates(),
        )

    attendees, result = meeting_attendees.mutate_meeting_attendees(
        (),
        request,
        readiness=_ready(),
        candidates=_candidates(),
        allow_outbound_prepare=True,
    )
    assert attendees[0].role is meeting_attendees.AttendeeRole.REQUIRED
    assert result.verified is True
    assert result.invitation_sent is False


def test_attendee_role_can_change_and_remove_is_idempotent() -> None:
    existing = (
        meeting_attendees.SyntheticMeetingAttendee(
            meeting_key="meeting-001",
            participant_key="room-blue",
            role=meeting_attendees.AttendeeRole.RESOURCE,
        ),
    )
    upsert = meeting_attendees.AttendeeMutationRequest(
        meeting_attendees.AttendeeMutationAction.UPSERT,
        meeting_key="meeting-001",
        participant_key="room-blue",
        role=meeting_attendees.AttendeeRole.OPTIONAL,
    )
    attendees, result = meeting_attendees.mutate_meeting_attendees(
        existing,
        upsert,
        readiness=_ready(),
        candidates=_candidates(),
        allow_outbound_prepare=True,
    )
    assert result.changed is True
    assert attendees[0].role is meeting_attendees.AttendeeRole.OPTIONAL

    remove = meeting_attendees.AttendeeMutationRequest(
        meeting_attendees.AttendeeMutationAction.REMOVE,
        meeting_key="meeting-001",
        participant_key="room-blue",
    )
    attendees, result = meeting_attendees.mutate_meeting_attendees(
        attendees,
        remove,
        readiness=_ready(),
        candidates=_candidates(),
        allow_outbound_prepare=True,
    )
    assert attendees == ()
    attendees, result = meeting_attendees.mutate_meeting_attendees(
        attendees,
        remove,
        readiness=_ready(),
        candidates=_candidates(),
        allow_outbound_prepare=True,
    )
    assert result.changed is False


def test_attendee_identity_rejects_email_shape() -> None:
    with pytest.raises(ValueError, match="email address"):
        meeting_attendees.AttendeeMutationRequest(
            meeting_attendees.AttendeeMutationAction.UPSERT,
            meeting_key="meeting-001",
            participant_key="someone@example.invalid",
            role=meeting_attendees.AttendeeRole.REQUIRED,
        )


def test_out082_remains_reserved_and_not_public() -> None:
    outlook = default_application_registry().get(ApplicationKey.OUTLOOK)
    assert outlook.state is ApplicationState.RESERVED
    assert default_tool_registry().by_application("outlook") == ()
