from __future__ import annotations

import pytest

from m365_mcp.application_registry import ApplicationKey, ApplicationState
from m365_mcp.application_registry import default_application_registry
from m365_mcp.apps.outlook import mock_ui, pin_mutations, pin_snooze_reads, readiness
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


def test_pin_and_unpin_are_verified() -> None:
    fixture = mock_ui.default_outlook_fixture()
    pinned, first = pin_mutations.apply_fixture_pin_mutation(
        fixture,
        pin_mutations.PinMutationRequest(
            pin_mutations.PinMutationAction.PIN,
            "msg-001",
        ),
        readiness=_ready(),
        markers=(),
    )
    assert first.read_back_is_pinned is True
    assert first.changed is True

    unpinned, second = pin_mutations.apply_fixture_pin_mutation(
        fixture,
        pin_mutations.PinMutationRequest(
            pin_mutations.PinMutationAction.UNPIN,
            "msg-001",
        ),
        readiness=_ready(),
        markers=pinned,
    )
    assert unpinned == ()
    assert second.read_back_is_pinned is False
    assert second.verified is True


def test_repeated_pin_and_unpin_are_domain_idempotent() -> None:
    fixture = mock_ui.default_outlook_fixture()
    existing = (pin_snooze_reads.PinSnoozeMarker("msg-001", is_pinned=True),)
    same, first = pin_mutations.apply_fixture_pin_mutation(
        fixture,
        pin_mutations.PinMutationRequest(
            pin_mutations.PinMutationAction.PIN,
            "msg-001",
        ),
        readiness=_ready(),
        markers=existing,
    )
    assert same == existing
    assert first.changed is False

    unchanged, second = pin_mutations.apply_fixture_pin_mutation(
        fixture,
        pin_mutations.PinMutationRequest(
            pin_mutations.PinMutationAction.UNPIN,
            "msg-002",
        ),
        readiness=_ready(),
        markers=(),
    )
    assert unchanged == ()
    assert second.changed is False


def test_pin_refuses_implicit_unsnooze() -> None:
    fixture = mock_ui.default_outlook_fixture()
    markers = (
        pin_snooze_reads.PinSnoozeMarker(
            message_key="msg-002",
            snooze_state=pin_snooze_reads.SnoozeState.SNOOZED,
            snooze_until_day_offset=3,
        ),
    )
    with pytest.raises(ValueError, match="unsnoozed before pinning"):
        pin_mutations.apply_fixture_pin_mutation(
            fixture,
            pin_mutations.PinMutationRequest(
                pin_mutations.PinMutationAction.PIN,
                "msg-002",
            ),
            readiness=_ready(),
            markers=markers,
        )


def test_pin_request_binds_to_core_idempotency_and_resource_lock() -> None:
    request = pin_mutations.PinMutationRequest(
        pin_mutations.PinMutationAction.PIN,
        "msg-001",
    )
    identity = resource_state_identity(
        ApplicationKey.OUTLOOK,
        account_scope="professional_session",
        container_kind="folder",
        external_container_id="inbox",
        resource_kind="message",
        external_resource_id=request.message_key,
    )
    record = reserve_operation(
        "outlook_pin",
        identity,
        request.to_payload(),
        read_back_required=True,
    )
    lock = state_lock("mock-professional-account", identity)
    assert record.read_back_required is True
    assert lock.state_identity_digest == identity.identity_digest


def test_out035_remains_reserved_and_not_public() -> None:
    outlook = default_application_registry().get(ApplicationKey.OUTLOOK)
    assert outlook.state is ApplicationState.RESERVED
    assert default_tool_registry().by_application("outlook") == ()
