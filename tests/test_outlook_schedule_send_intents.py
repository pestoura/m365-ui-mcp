from __future__ import annotations

import pytest

from m365_mcp.application_registry import (
    ApplicationKey,
    ApplicationState,
    default_application_registry,
)
from m365_mcp.apps.outlook import (
    draft_models,
    outbound_models,
    readiness,
    schedule_send_intents,
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


def test_schedule_send_preparation_is_approval_required_and_not_executable() -> None:
    drafts = (draft_models.SyntheticDraft("draft-001", to_keys=("person-alpha",)),)
    intent = schedule_send_intents.prepare_schedule_send_intent(
        drafts,
        intent_key="intent-049",
        draft_key="draft-001",
        scheduled_slot="slot-2026-08-10T09:00Z",
        readiness=_ready(),
    )
    assert intent.kind is outbound_models.OutboundIntentKind.SCHEDULE_SEND
    assert (
        intent.approval_state
        is outbound_models.OutboundApprovalState.REQUIRED_NOT_BOUND
    )
    assert intent.executable is False
    with pytest.raises(PermissionError, match="canonical HITL approval"):
        outbound_models.require_outbound_execution_blocked(intent)


def test_schedule_send_requires_recipient() -> None:
    with pytest.raises(ValueError, match="at least one recipient"):
        schedule_send_intents.prepare_schedule_send_intent(
            draft_models.default_synthetic_drafts(),
            intent_key="intent-049",
            draft_key="draft-001",
            scheduled_slot="slot-2026-08-10T09:00Z",
            readiness=_ready(),
        )


def test_out049_remains_reserved_and_not_public() -> None:
    outlook = default_application_registry().get(ApplicationKey.OUTLOOK)
    assert outlook.state is ApplicationState.RESERVED
    assert default_tool_registry().by_application("outlook") == ()
