from __future__ import annotations

import pytest

from m365_mcp.application_registry import (
    ApplicationKey,
    ApplicationState,
    default_application_registry,
)
from m365_mcp.apps.outlook import message_move_mutations, mock_ui, readiness
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


def test_message_move_and_read_back_are_verified() -> None:
    fixture = mock_ui.default_outlook_fixture()
    updated, result = message_move_mutations.apply_fixture_message_move(
        fixture,
        message_move_mutations.MessageMoveRequest("msg-001", "sent"),
        readiness=_ready(),
    )
    moved = next(item for item in updated.messages if item.message_key == "msg-001")
    assert result.previous_folder_key == "inbox"
    assert result.read_back_folder_key == "sent"
    assert result.changed is True
    assert result.verified is True
    assert moved.folder_key == "sent"


def test_repeated_move_is_domain_idempotent() -> None:
    fixture = mock_ui.default_outlook_fixture()
    unchanged, result = message_move_mutations.apply_fixture_message_move(
        fixture,
        message_move_mutations.MessageMoveRequest("msg-002", "archive"),
        readiness=_ready(),
    )
    assert unchanged == fixture
    assert result.changed is False
    assert result.verified is True


def test_move_rejects_unknown_folder_and_message() -> None:
    fixture = mock_ui.default_outlook_fixture()
    with pytest.raises(ValueError, match="target folder"):
        message_move_mutations.apply_fixture_message_move(
            fixture,
            message_move_mutations.MessageMoveRequest("msg-001", "missing"),
            readiness=_ready(),
        )
    with pytest.raises(ValueError, match="message_key"):
        message_move_mutations.apply_fixture_message_move(
            fixture,
            message_move_mutations.MessageMoveRequest("msg-missing", "inbox"),
            readiness=_ready(),
        )


def test_move_request_binds_to_core_idempotency_and_resource_lock() -> None:
    request = message_move_mutations.MessageMoveRequest("msg-001", "sent")
    identity = resource_state_identity(
        ApplicationKey.OUTLOOK,
        account_scope="professional_session",
        container_kind="folder",
        external_container_id="inbox",
        resource_kind="message",
        external_resource_id=request.message_key,
    )
    record = reserve_operation(
        "outlook_message_move",
        identity,
        request.to_payload(),
        read_back_required=True,
    )
    lock = state_lock("mock-professional-account", identity)
    assert record.read_back_required is True
    assert lock.state_identity_digest == identity.identity_digest


def test_out038_remains_reserved_and_not_public() -> None:
    outlook = default_application_registry().get(ApplicationKey.OUTLOOK)
    assert outlook.state is ApplicationState.RESERVED
    assert default_tool_registry().by_application("outlook") == ()
