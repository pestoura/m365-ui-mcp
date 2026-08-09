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
    reply_all_intents,
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


def test_reply_all_preparation_is_approval_required_and_not_executable() -> None:
    intent = reply_all_intents.prepare_reply_all_intent(
        draft_models.default_synthetic_drafts(),
        mock_ui.default_outlook_fixture(),
        intent_key="intent-052",
        draft_key="draft-001",
        source_message_key="msg-001",
        readiness=_ready(),
    )
    assert intent.kind is outbound_models.OutboundIntentKind.REPLY_ALL
    assert intent.approval_state is outbound_models.OutboundApprovalState.REQUIRED_NOT_BOUND
    assert intent.executable is False
    with pytest.raises(PermissionError, match="canonical HITL approval"):
        outbound_models.require_outbound_execution_blocked(intent)


def test_reply_all_requires_known_source_message() -> None:
    with pytest.raises(ValueError, match="source_message_key"):
        reply_all_intents.prepare_reply_all_intent(
            draft_models.default_synthetic_drafts(),
            mock_ui.default_outlook_fixture(),
            intent_key="intent-052",
            draft_key="draft-001",
            source_message_key="msg-missing",
            readiness=_ready(),
        )


def test_out052_remains_reserved_and_not_public() -> None:
    outlook = default_application_registry().get(ApplicationKey.OUTLOOK)
    assert outlook.state is ApplicationState.RESERVED
    assert default_tool_registry().by_application("outlook") == ()
