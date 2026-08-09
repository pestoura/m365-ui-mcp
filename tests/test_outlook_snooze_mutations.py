from __future__ import annotations

import pytest

from m365_mcp.application_registry import (
    ApplicationKey,
    ApplicationState,
    default_application_registry,
)
from m365_mcp.apps.outlook import mock_ui, pin_snooze_reads, readiness, snooze_mutations
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


def test_snooze_and_unsnooze_are_verified() -> None:
    fixture = mock_ui.default_outlook_fixture()
    snoozed, first = snooze_mutations.apply_fixture_snooze_mutation(
        fixture,
        snooze_mutations.SnoozeMutationRequest(
            snooze_mutations.SnoozeMutationAction.SNOOZE,
            "msg-001",
            snooze_until_day_offset=4,
        ),
        readiness=_ready(),
        markers=(),
    )
    assert first.read_back_state is pin_snooze_reads.SnoozeState.SNOOZED
    assert first.read_back_until_day_offset == 4
    assert first.verified is True

    unsnoozed, second = snooze_mutations.apply_fixture_snooze_mutation(
        fixture,
        snooze_mutations.SnoozeMutationRequest(
            snooze_mutations.SnoozeMutationAction.UNSNOOZE,
            "msg-001",
        ),
        readiness=_ready(),
        markers=snoozed,
    )
    assert unsnoozed == ()
    assert second.read_back_state is pin_snooze_reads.SnoozeState.NOT_SNOOZED
    assert second.read_back_until_day_offset is None


def test_repeated_snooze_is_domain_idempotent() -> None:
    fixture = mock_ui.default_outlook_fixture()
    markers = (
        pin_snooze_reads.PinSnoozeMarker(
            message_key="msg-001",
            snooze_state=pin_snooze_reads.SnoozeState.SNOOZED,
            snooze_until_day_offset=4,
        ),
    )
    updated, result = snooze_mutations.apply_fixture_snooze_mutation(
        fixture,
        snooze_mutations.SnoozeMutationRequest(
            snooze_mutations.SnoozeMutationAction.SNOOZE,
            "msg-001",
            snooze_until_day_offset=4,
        ),
        readiness=_ready(),
        markers=markers,
    )
    assert updated == markers
    assert result.changed is False


def test_snooze_refuses_implicit_unpin_and_invalid_offset() -> None:
    fixture = mock_ui.default_outlook_fixture()
    markers = (pin_snooze_reads.PinSnoozeMarker("msg-001", is_pinned=True),)
    with pytest.raises(ValueError, match="unpinned before snoozing"):
        snooze_mutations.apply_fixture_snooze_mutation(
            fixture,
            snooze_mutations.SnoozeMutationRequest(
                snooze_mutations.SnoozeMutationAction.SNOOZE,
                "msg-001",
                snooze_until_day_offset=4,
            ),
            readiness=_ready(),
            markers=markers,
        )
    with pytest.raises(ValueError, match="bounded"):
        snooze_mutations.SnoozeMutationRequest(
            snooze_mutations.SnoozeMutationAction.SNOOZE,
            "msg-001",
            snooze_until_day_offset=4000,
        )


def test_snooze_binds_to_core_idempotency_and_resource_lock() -> None:
    request = snooze_mutations.SnoozeMutationRequest(
        snooze_mutations.SnoozeMutationAction.SNOOZE,
        "msg-001",
        snooze_until_day_offset=4,
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
        "outlook_snooze",
        identity,
        request.to_payload(),
        read_back_required=True,
    )
    lock = state_lock("mock-professional-account", identity)
    assert record.read_back_required is True
    assert lock.state_identity_digest == identity.identity_digest


def test_out036_remains_reserved_and_not_public() -> None:
    outlook = default_application_registry().get(ApplicationKey.OUTLOOK)
    assert outlook.state is ApplicationState.RESERVED
    assert default_tool_registry().by_application("outlook") == ()
