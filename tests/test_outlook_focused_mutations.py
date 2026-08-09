from __future__ import annotations

import pytest

from m365_mcp.application_registry import (
    ApplicationKey,
    ApplicationState,
    default_application_registry,
)
from m365_mcp.apps.outlook import focused_mutations, mock_ui, readiness
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


def test_focused_and_other_moves_are_verified() -> None:
    fixture = mock_ui.default_outlook_fixture()
    markers, first = focused_mutations.apply_fixture_focused_mutation(
        fixture,
        focused_mutations.FocusedMutationRequest(
            focused_mutations.FocusedMutationAction.MOVE_TO_FOCUSED,
            "msg-001",
        ),
        readiness=_ready(),
    )
    assert first.read_back_class is focused_mutations.FocusedInboxClass.FOCUSED
    assert first.changed is True

    markers, second = focused_mutations.apply_fixture_focused_mutation(
        fixture,
        focused_mutations.FocusedMutationRequest(
            focused_mutations.FocusedMutationAction.MOVE_TO_OTHER,
            "msg-001",
        ),
        readiness=_ready(),
        markers=markers,
    )
    assert second.previous_class is focused_mutations.FocusedInboxClass.FOCUSED
    assert second.read_back_class is focused_mutations.FocusedInboxClass.OTHER
    assert second.verified is True
    assert markers[0].classification is focused_mutations.FocusedInboxClass.OTHER


def test_repeated_focused_move_is_domain_idempotent() -> None:
    fixture = mock_ui.default_outlook_fixture()
    existing = (
        focused_mutations.FocusedInboxMarker(
            "msg-001",
            focused_mutations.FocusedInboxClass.FOCUSED,
        ),
    )
    same, result = focused_mutations.apply_fixture_focused_mutation(
        fixture,
        focused_mutations.FocusedMutationRequest(
            focused_mutations.FocusedMutationAction.MOVE_TO_FOCUSED,
            "msg-001",
        ),
        readiness=_ready(),
        markers=existing,
    )
    assert same == existing
    assert result.changed is False
    assert result.verified is True


def test_focused_movement_requires_inbox_message() -> None:
    fixture = mock_ui.default_outlook_fixture()
    with pytest.raises(ValueError, match="Inbox message"):
        focused_mutations.apply_fixture_focused_mutation(
            fixture,
            focused_mutations.FocusedMutationRequest(
                focused_mutations.FocusedMutationAction.MOVE_TO_OTHER,
                "msg-002",
            ),
            readiness=_ready(),
        )


def test_focused_request_binds_to_core_idempotency_and_resource_lock() -> None:
    request = focused_mutations.FocusedMutationRequest(
        focused_mutations.FocusedMutationAction.MOVE_TO_FOCUSED,
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
        "outlook_focused_move",
        identity,
        request.to_payload(),
        read_back_required=True,
    )
    lock = state_lock("mock-professional-account", identity)
    assert record.read_back_required is True
    assert lock.state_identity_digest == identity.identity_digest


def test_out040_remains_reserved_and_not_public() -> None:
    outlook = default_application_registry().get(ApplicationKey.OUTLOOK)
    assert outlook.state is ApplicationState.RESERVED
    assert default_tool_registry().by_application("outlook") == ()
