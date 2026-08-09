from __future__ import annotations

import pytest

from m365_mcp.application_registry import (
    ApplicationKey,
    ApplicationState,
    default_application_registry,
)
from m365_mcp.apps.outlook import flag_mutations, follow_up_reads, mock_ui, readiness
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


def test_flag_unflag_and_complete_are_verified() -> None:
    fixture = mock_ui.default_outlook_fixture()
    flags: tuple[follow_up_reads.FollowUpFlag, ...] = ()

    flagged, first = flag_mutations.apply_fixture_flag_mutation(
        fixture,
        flag_mutations.FlagMutationRequest(
            flag_mutations.FlagMutationAction.FLAG,
            "msg-001",
        ),
        readiness=_ready(),
        flags=flags,
    )
    assert first.read_back_state is follow_up_reads.FollowUpState.FLAGGED
    assert first.changed is True

    completed, second = flag_mutations.apply_fixture_flag_mutation(
        fixture,
        flag_mutations.FlagMutationRequest(
            flag_mutations.FlagMutationAction.COMPLETE,
            "msg-001",
            completed_day_offset=0,
        ),
        readiness=_ready(),
        flags=flagged,
    )
    assert second.read_back_state is follow_up_reads.FollowUpState.COMPLETED

    unflagged, third = flag_mutations.apply_fixture_flag_mutation(
        fixture,
        flag_mutations.FlagMutationRequest(
            flag_mutations.PinMutationAction.UNPIN,
            "msg-001",
        ),
        readiness=_ready(),
        flags=completed,
    )
    assert unflagged == ()
    assert third.read_back_state is follow_up_reads.FollowUpState.NOT_FLAGGED


def test_complete_requires_existing_flag_and_bounded_day() -> None:
    fixture = mock_ui.default_outlook_fixture()
    with pytest.raises(ValueError, match="existing flagged"):
        flag_mutations.apply_fixture_flag_mutation(
            fixture,
            flag_mutations.FlagMutationRequest(
                flag_mutations.FlagMutationAction.COMPLETE,
                "msg-001",
                completed_day_offset=0,
            ),
            readiness=_ready(),
            flags=(),
        )
    with pytest.raises(ValueError, match="bounded"):
        flag_mutations.FlagMutationRequest(
            flag_mutations.FlagMutationAction.COMPLETE,
            "msg-001",
            completed_day_offset=4000,
        )


def test_repeated_flag_is_domain_idempotent() -> None:
    fixture = mock_ui.default_outlook_fixture()
    existing = (
        follow_up_reads.FollowUpFlag(
            message_key="msg-001",
            state=follow_up_reads.FollowUpState.FLAGGED,
        ),
    )
    updated, result = flag_mutations.apply_fixture_flag_mutation(
        fixture,
        flag_mutations.FlagMutationRequest(
            flag_mutations.FlagMutationAction.FLAG,
            "msg-001",
        ),
        readiness=_ready(),
        flags=existing,
    )
    assert updated == existing
    assert result.changed is False


def test_flag_request_binds_to_core_idempotency_and_resource_lock() -> None:
    request = flag_mutations.FlagMutationRequest(
        flag_mutations.FlagMutationAction.FLAG,
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
        "outlook_flag",
        identity,
        request.to_payload(),
        read_back_required=True,
    )
    lock = state_lock("mock-professional-account", identity)
    assert record.identity_digest == identity.identity_digest
    assert lock.state_identity_digest == identity.identity_digest


def test_out033_remains_reserved_and_not_public() -> None:
    outlook = default_application_registry().get(ApplicationKey.OUTLOOK)
    assert outlook.state is ApplicationState.RESERVED
    assert default_tool_registry().by_application("outlook") == ()


# Revalidated against cumulative Wave B through OUT-032; no live claim.
