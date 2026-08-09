from __future__ import annotations

import pytest

from m365_mcp.application_registry import (
    ApplicationKey,
    ApplicationState,
    default_application_registry,
)
from m365_mcp.apps.outlook import mock_ui, outbound_models, readiness, recall_intents
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


def _sent_fixture() -> mock_ui.OutlookMockFixture:
    fixture = mock_ui.default_outlook_fixture()
    return mock_ui.OutlookMockFixture(
        fixture_version=fixture.fixture_version,
        synthetic=True,
        mailbox_key=fixture.mailbox_key,
        folders=fixture.folders,
        messages=fixture.messages
        + (
            mock_ui.MockMessage(
                message_key="msg-sent-001",
                subject="Synthetic sent message",
                folder_key="sent",
                is_read=True,
            ),
        ),
    )


def test_recall_preparation_is_approval_required_and_not_executable() -> None:
    intent = recall_intents.prepare_recall_intent(
        _sent_fixture(),
        intent_key="intent-056",
        sent_message_key="msg-sent-001",
        readiness=_ready(),
    )
    assert intent.approval_state is outbound_models.OutboundApprovalState.REQUIRED_NOT_BOUND
    assert intent.executable is False
    with pytest.raises(PermissionError, match="canonical HITL approval"):
        recall_intents.require_recall_execution_blocked(intent)


def test_recall_rejects_non_sent_source() -> None:
    with pytest.raises(ValueError, match="sent item"):
        recall_intents.prepare_recall_intent(
            mock_ui.default_outlook_fixture(),
            intent_key="intent-056",
            sent_message_key="msg-001",
            readiness=_ready(),
        )


def test_out056_remains_reserved_and_not_public() -> None:
    outlook = default_application_registry().get(ApplicationKey.OUTLOOK)
    assert outlook.state is ApplicationState.RESERVED
    assert default_tool_registry().by_application("outlook") == ()
