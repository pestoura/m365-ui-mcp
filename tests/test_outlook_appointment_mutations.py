from __future__ import annotations

from m365_mcp.application_registry import (
    ApplicationKey,
    ApplicationState,
    default_application_registry,
)
from m365_mcp.apps.outlook import appointment_mutations, calendar_events, readiness
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


def _event(subject: str = "Synthetic appointment") -> calendar_events.SyntheticEvent:
    return calendar_events.SyntheticEvent(
        event_key="apt-001",
        calendar_key="cal-primary",
        subject=subject,
        start_day_offset=1,
        start_minute_of_day=540,
        duration_minutes=45,
    )


def test_appointment_create_update_delete_has_exact_readback() -> None:
    create = appointment_mutations.AppointmentMutationRequest(
        appointment_mutations.AppointmentMutationAction.CREATE,
        event=_event(),
    )
    events, result = appointment_mutations.mutate_appointments(
        (), create, readiness=_ready()
    )
    assert result.read_back == _event()
    assert result.verified is True

    update = appointment_mutations.AppointmentMutationRequest(
        appointment_mutations.AppointmentMutationAction.UPDATE,
        event=_event("Synthetic appointment updated"),
    )
    events, result = appointment_mutations.mutate_appointments(
        events, update, readiness=_ready()
    )
    assert result.read_back == _event("Synthetic appointment updated")
    assert result.changed is True

    delete = appointment_mutations.AppointmentMutationRequest(
        appointment_mutations.AppointmentMutationAction.DELETE,
        event_key="apt-001",
    )
    events, result = appointment_mutations.mutate_appointments(
        events, delete, readiness=_ready()
    )
    assert events == ()
    assert result.read_back is None

    events, result = appointment_mutations.mutate_appointments(
        events, delete, readiness=_ready()
    )
    assert result.changed is False


def test_appointment_request_binds_to_idempotency_and_lock() -> None:
    request = appointment_mutations.AppointmentMutationRequest(
        appointment_mutations.AppointmentMutationAction.CREATE,
        event=_event(),
    )
    identity = resource_state_identity(
        ApplicationKey.OUTLOOK,
        account_scope="professional_session",
        container_kind="calendar",
        external_container_id="cal-primary",
        resource_kind="appointment",
        external_resource_id="apt-001",
    )
    record = reserve_operation(
        "outlook_appointment_mutation",
        identity,
        request.to_payload(),
        read_back_required=True,
    )
    lock = state_lock("mock-professional-account", identity)
    assert record.read_back_required is True
    assert lock.state_identity_digest == identity.identity_digest


def test_out080_remains_reserved_and_not_public() -> None:
    outlook = default_application_registry().get(ApplicationKey.OUTLOOK)
    assert outlook.state is ApplicationState.RESERVED
    assert default_tool_registry().by_application("outlook") == ()
