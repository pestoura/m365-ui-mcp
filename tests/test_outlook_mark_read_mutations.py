from __future__ import annotations

import pytest

from m365_mcp.application_registry import (
    ApplicationKey,
    ApplicationState,
    default_application_registry,
)
from m365_mcp.apps.outlook import mark_read_mutations, mock_ui, readiness
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


def test_mark_read_and_unread_are_verified_by_read_back() -> None:
    fixture = mock_ui.default_outlook_fixture()
    request = mark_read_mutations.MessageReadMutationRequest("msg-001", True)
    updated, result = mark_read_mutations.apply_fixture_message_read_state(
        fixture,
        request,
        readiness=_ready(),
    )
    assert fixture.messages[0].is_read is False
    assert updated.messages[0].is_read is True
    assert result.previous_is_read is False
    assert result.read_back_is_read is True
    assert result.changed is True
    assert result.verified is True

    reverted, second = mark_read_mutations.apply_fixture_message_read_state(
        updated,
        mark_read_mutations.MessageReadMutationRequest("msg-001", False),
        readiness=_ready(),
    )
    assert reverted.messages[0].is_read is False
    assert second.read_back_is_read is False
    assert second.verified is True


def test_same_state_is_idempotent_at_domain_level() -> None:
    fixture = mock_ui.default_outlook_fixture()
    updated, result = mark_read_mutations.apply_fixture_message_read_state(
        fixture,
        mark_read_mutations.MessageReadMutationRequest("msg-002", True),
        readiness=_ready(),
    )
    assert updated.messages == fixture.messages
    assert result.changed is False
    assert result.verified is True


def test_invalid_or_unknown_message_fails_closed() -> None:
    fixture = mock_ui.default_outlook_fixture()
    with pytest.raises(ValueError, match="semantic token"):
        mark_read_mutations.MessageReadMutationRequest(" msg-001", True)
    with pytest.raises(ValueError, match="not found"):
        mark_read_mutations.apply_fixture_message_read_state(
            fixture,
            mark_read_mutations.MessageReadMutationRequest("missing", True),
            readiness=_ready(),
        )


def test_request_binds_to_core_idempotency_and_typed_lock_models() -> None:
    request = mark_read_mutations.MessageReadMutationRequest("msg-001", True)
    identity = resource_state_identity(
        ApplicationKey.OUTLOOK,
        account_scope="professional_session",
        container_kind="folder",
        external_container_id="inbox",
        resource_kind="message",
        external_resource_id=request.message_key,
    )
    record = reserve_operation(
        "outlook_mark_read",
        identity,
        request.to_payload(),
        read_back_required=True,
    )
    lock = state_lock("mock-professional-account", identity)
    assert record.read_back_required is True
    assert record.identity_digest == identity.identity_digest
    assert lock.application is ApplicationKey.OUTLOOK
    assert lock.state_identity_digest == identity.identity_digest


def test_out030_remains_reserved_and_not_publicly_registered() -> None:
    outlook = default_application_registry().get(ApplicationKey.OUTLOOK)
    assert outlook.state is ApplicationState.RESERVED
    assert default_tool_registry().by_application("outlook") == ()


def test_projection_excludes_browser_and_session_primitives() -> None:
    fixture = mock_ui.default_outlook_fixture()
    _, result = mark_read_mutations.apply_fixture_message_read_state(
        fixture,
        mark_read_mutations.MessageReadMutationRequest("msg-001", True),
        readiness=_ready(),
    )
    projection = repr(result.to_projection()).lower()
    for forbidden in (
        "http",
        "://",
        "selector",
        "xpath",
        "javascript",
        "cookie",
        "token",
        "storage_state",
    ):
        assert forbidden not in projection


# Revalidated against the current Wave B integration base; no live-support claim.
