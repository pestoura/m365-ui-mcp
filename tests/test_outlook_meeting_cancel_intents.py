from __future__ import annotations

import pytest

from m365_mcp.application_registry import (
    ApplicationKey,
    ApplicationState,
    default_application_registry,
)
from m365_mcp.apps.outlook import meeting_cancel_intents, readiness
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


def _intent() -> meeting_cancel_intents.SyntheticMeetingCancellationIntent:
    return meeting_cancel_intents.SyntheticMeetingCancellationIntent(
        meeting_key="meeting-001",
        message_text="Synthetic cancellation context",
    )


def test_cancellation_requires_both_prepare_allowances_and_never_executes() -> None:
    with pytest.raises(PermissionError, match="outbound-prepare"):
        meeting_cancel_intents.prepare_meeting_cancellation(
            (), _intent(), readiness=_ready()
        )
    with pytest.raises(PermissionError, match="cancellation-prepare"):
        meeting_cancel_intents.prepare_meeting_cancellation(
            (),
            _intent(),
            readiness=_ready(),
            allow_outbound_prepare=True,
        )

    intents, result = meeting_cancel_intents.prepare_meeting_cancellation(
        (),
        _intent(),
        readiness=_ready(),
        allow_outbound_prepare=True,
        allow_cancellation_prepare=True,
    )
    assert intents == (_intent(),)
    assert result.cancelled is False
    assert result.cancellation_sent is False
    assert result.verified is True


def test_cancellation_message_rejects_nul() -> None:
    with pytest.raises(ValueError, match="NUL"):
        meeting_cancel_intents.SyntheticMeetingCancellationIntent(
            meeting_key="meeting-001",
            message_text="bad\x00message",
        )


def test_out090_remains_reserved_and_not_public() -> None:
    outlook = default_application_registry().get(ApplicationKey.OUTLOOK)
    assert outlook.state is ApplicationState.RESERVED
    assert default_tool_registry().by_application("outlook") == ()
