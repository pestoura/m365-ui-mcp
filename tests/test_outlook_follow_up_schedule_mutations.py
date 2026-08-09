from __future__ import annotations

import pytest

from m365_mcp.application_registry import ApplicationKey, ApplicationState
from m365_mcp.application_registry import default_application_registry
from m365_mcp.apps.outlook import (
    follow_up_reads,
    follow_up_schedule_mutations,
    mock_ui,
    readiness,
)
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


def test_due_and_reminder_are_verified_by_read_back() -> None:
    fixture = mock_ui.default_outlook_fixture()
    flags = follow_up_reads.default_synthetic_follow_up_flags()
    updated, result = follow_up_schedule_mutations.apply_fixture_follow_up_schedule(
        fixture,
        follow_up_schedule_mutations.FollowUpScheduleMutationRequest(
            "msg-001",
            due_day_offset=5,
            start_day_offset=1,
            reminder_day_offset=3,
        ),
        readiness=_ready(),
        flags=flags,
    )
    assert result.read_back_start_day_offset == 1
    assert result.read_back_due_day_offset == 5
    assert result.read_back_reminder_day_offset == 3
    assert result.verified is True

    state = follow_up_reads.read_fixture_follow_up_state(
        fixture,
        "msg-001",
        readiness=_ready(),
        flags=updated,
    )
    assert state.reminder_day_offset == 3


def test_repeated_schedule_is_domain_idempotent() -> None:
    fixture = mock_ui.default_outlook_fixture()
    flags = (
        follow_up_reads.FollowUpFlag(
            message_key="msg-001",
            state=follow_up_reads.FollowUpState.FLAGGED,
            start_day_offset=1,
            due_day_offset=5,
            reminder_day_offset=3,
        ),
    )
    updated, result = follow_up_schedule_mutations.apply_fixture_follow_up_schedule(
        fixture,
        follow_up_schedule_mutations.FollowUpScheduleMutationRequest(
            "msg-001",
            due_day_offset=5,
            start_day_offset=1,
            reminder_day_offset=3,
        ),
        readiness=_ready(),
        flags=flags,
    )
    assert updated == flags
    assert result.changed is False


def test_invalid_schedule_and_non_flagged_target_fail_closed() -> None:
    with pytest.raises(ValueError, match="must not follow"):
        follow_up_schedule_mutations.FollowUpScheduleMutationRequest(
            "msg-001",
            due_day_offset=2,
            reminder_day_offset=3,
        )

    fixture = mock_ui.default_outlook_fixture()
    with pytest.raises(ValueError, match="existing flagged"):
        follow_up_schedule_mutations.apply_fixture_follow_up_schedule(
            fixture,
            follow_up_schedule_mutations.FollowUpScheduleMutationRequest(
                "msg-001",
                due_day_offset=2,
            ),
            readiness=_ready(),
            flags=(),
        )


def test_schedule_binds_to_core_idempotency_and_resource_lock() -> None:
    request = follow_up_schedule_mutations.FollowUpScheduleMutationRequest(
        "msg-001",
        due_day_offset=5,
        reminder_day_offset=3,
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
        "outlook_follow_up_schedule",
        identity,
        request.to_payload(),
        read_back_required=True,
    )
    lock = state_lock("mock-professional-account", identity)
    assert record.read_back_required is True
    assert lock.state_identity_digest == identity.identity_digest


def test_out034_remains_reserved_and_not_public() -> None:
    outlook = default_application_registry().get(ApplicationKey.OUTLOOK)
    assert outlook.state is ApplicationState.RESERVED
    assert default_tool_registry().by_application("outlook") == ()
