from __future__ import annotations

import pytest

from m365_mcp.application_registry import (
    ApplicationKey,
    ApplicationState,
    default_application_registry,
)
from m365_mcp.apps.outlook import (
    draft_models,
    mock_ui,
    outbound_models,
    readiness,
    resend_intents,
)
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


def test_resend_preparation_is_approval_required_and_not_executable() -> None:
    drafts = (draft_models.SyntheticDraft("draft-001", to_keys=("person-alpha",)),)
    intent = resend_intents.prepare_resend_intent(
        drafts,
        _sent_fixture(),
        intent_key="intent-054",
        draft_key="draft-001",
        source_message_key="msg-sent-001",
        readiness=_ready(),
    )
    assert intent.kind is outbound_models.OutboundIntentKind.RESEND
    assert intent.approval_state is outbound_models.OutboundApprovalState.REQUIRED_NOT_BOUND
    assert intent.executable is False
    with pytest.raises(PermissionError, match="canonical HITL approval"):
        outbound_models.require_outbound_execution_blocked(intent)


def test_resend_rejects_non_sent_source_and_missing_recipient() -> None:
    drafts = (draft_models.SyntheticDraft("draft-001", to_keys=("person-alpha",)),)
    with pytest.raises(ValueError, match="sent item"):
        resend_intents.prepare_resend_intent(
            drafts,
            mock_ui.default_outlook_fixture(),
            intent_key="intent-054",
            draft_key="draft-001",
            source_message_key="msg-001",
            readiness=_ready(),
        )

    with pytest.raises(ValueError, match="at least one recipient"):
        resend_intents.prepare_resend_intent(
            draft_models.default_synthetic_drafts(),
            _sent_fixture(),
            intent_key="intent-054",
            draft_key="draft-001",
            source_message_key="msg-sent-001",
            readiness=_ready(),
        )


def test_out054_remains_reserved_and_not_public() -> None:
    outlook = default_application_registry().get(ApplicationKey.OUTLOOK)
    assert outlook.state is ApplicationState.RESERVED
    assert default_tool_registry().by_application("outlook") == ()
