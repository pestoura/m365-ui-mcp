from __future__ import annotations

import pytest

from m365_mcp.application_registry import (
    ApplicationKey,
    ApplicationState,
    default_application_registry,
)
from m365_mcp.apps.outlook import calendar_events, meeting_mutations, readiness
from m365_mcp.idempotency_v2 import reserve_operation
from m365_mcp.state_identity import resource_state_identity
from m365_mcp.tool_registry import default_tool_registry
from m365_mcp.typed_locks import state_lock


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


def _meeting(subject: str = "Synthetic meeting") -> meeting_mutations.SyntheticMeeting:
    return meeting_mutations.SyntheticMeeting(
        meeting_key="meeting-001",
        event=calendar_events.SyntheticEvent(
            event_key="meeting-event-001",
            calendar_key="cal-primary",
            subject=subject,
            start_day_offset=2,
            start_minute_of_day=600,
            duration_minutes=30,
        ),
    )


def test_meeting_definition_requires_prepare_allowance_and_never_sends() -> None:
    request = meeting_mutations.MeetingMutationRequest(
        meeting_mutations.MeetingMutationAction.CREATE,
        _meeting(),
    )
    with pytest.raises(PermissionError, match="outbound-prepare"):
        meeting_mutations.prepare_meeting_mutation((), request, readiness=_ready())

    meetings, result = meeting_mutations.prepare_meeting_mutation(
        (),
        request,
        readiness=_ready(),
        allow_outbound_prepare=True,
    )
    assert meetings == (_meeting(),)
    assert result.read_back == _meeting()
    assert result.invitation_sent is False
    assert (
        result.disposition
        is meeting_mutations.MeetingMutationDisposition.PREPARED_NOT_SENT
    )


def test_meeting_update_is_read_back_and_idempotent() -> None:
    existing = (_meeting(),)
    request = meeting_mutations.MeetingMutationRequest(
        meeting_mutations.MeetingMutationAction.UPDATE,
        _meeting("Synthetic meeting updated"),
    )
    meetings, result = meeting_mutations.prepare_meeting_mutation(
        existing,
        request,
        readiness=_ready(),
        allow_outbound_prepare=True,
    )
    assert result.changed is True
    meetings, result = meeting_mutations.prepare_meeting_mutation(
        meetings,
        request,
        readiness=_ready(),
        allow_outbound_prepare=True,
    )
    assert result.changed is False


def test_meeting_request_binds_to_idempotency_and_lock() -> None:
    request = meeting_mutations.MeetingMutationRequest(
        meeting_mutations.MeetingMutationAction.CREATE,
        _meeting(),
    )
    identity = resource_state_identity(
        ApplicationKey.OUTLOOK,
        account_scope="professional_session",
        container_kind="calendar",
        external_container_id="cal-primary",
        resource_kind="meeting",
        external_resource_id="meeting-001",
    )
    record = reserve_operation(
        "outlook_meeting_prepare",
        identity,
        request.to_payload(),
        read_back_required=True,
    )
    lock = state_lock("mock-professional-account", identity)
    assert record.read_back_required is True
    assert lock.state_identity_digest == identity.identity_digest


def test_out081_remains_reserved_and_not_public() -> None:
    outlook = default_application_registry().get(ApplicationKey.OUTLOOK)
    assert outlook.state is ApplicationState.RESERVED
    assert default_tool_registry().by_application("outlook") == ()
