from __future__ import annotations

import pytest

from m365_mcp.application_registry import (
    ApplicationKey,
    ApplicationState,
    default_application_registry,
)
from m365_mcp.apps.outlook import meeting_forward_intents, readiness, recipient_resolution
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


def _candidates() -> tuple[recipient_resolution.SyntheticRecipientCandidate, ...]:
    return (
        recipient_resolution.SyntheticRecipientCandidate(
            recipient_key="person-alpha",
            aliases=("alpha",),
        ),
    )


def _intent() -> meeting_forward_intents.SyntheticMeetingForwardIntent:
    return meeting_forward_intents.SyntheticMeetingForwardIntent(
        meeting_key="meeting-001",
        recipient_keys=("person-alpha",),
    )


def test_forward_requires_prepare_allowance_and_never_dispatches() -> None:
    with pytest.raises(PermissionError, match="outbound-prepare"):
        meeting_forward_intents.prepare_meeting_forward(
            (),
            _intent(),
            readiness=_ready(),
            candidates=_candidates(),
        )

    intents, result = meeting_forward_intents.prepare_meeting_forward(
        (),
        _intent(),
        readiness=_ready(),
        candidates=_candidates(),
        allow_outbound_prepare=True,
    )
    assert intents == (_intent(),)
    assert result.forwarded is False
    assert result.verified is True


def test_forward_rejects_email_shape_and_unknown_recipient() -> None:
    with pytest.raises(ValueError, match="email address"):
        meeting_forward_intents.SyntheticMeetingForwardIntent(
            meeting_key="meeting-001",
            recipient_keys=("someone@example.invalid",),
        )

    unknown = meeting_forward_intents.SyntheticMeetingForwardIntent(
        meeting_key="meeting-001",
        recipient_keys=("person-unknown",),
    )
    with pytest.raises(ValueError, match="known synthetic candidate"):
        meeting_forward_intents.prepare_meeting_forward(
            (),
            unknown,
            readiness=_ready(),
            candidates=_candidates(),
            allow_outbound_prepare=True,
        )


def test_out089_remains_reserved_and_not_public() -> None:
    outlook = default_application_registry().get(ApplicationKey.OUTLOOK)
    assert outlook.state is ApplicationState.RESERVED
    assert default_tool_registry().by_application("outlook") == ()
