from __future__ import annotations

import pytest

from m365_mcp.application_registry import (
    ApplicationKey,
    ApplicationState,
    default_application_registry,
)
from m365_mcp.apps.outlook import (
    ooo_cancel_existing_meetings,
    ooo_schedule,
    readiness,
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


def test_cancel_existing_meetings_is_bounded_governed_intent_only() -> None:
    intent = ooo_cancel_existing_meetings.prepare_ooo_meeting_cancellations(
        intent_key="ooo-cancel-001",
        event_keys=("event-001", "event-002"),
        schedule=ooo_schedule.OooSchedule(120, 360),
        readiness=_ready(),
    )
    assert intent.event_keys == ("event-001", "event-002")
    assert intent.executable is False
    assert intent.dispatched is False
    assert intent.to_projection()["approval_required"] is True


def test_cancel_existing_meetings_rejects_identity_shape() -> None:
    with pytest.raises(ValueError, match="opaque"):
        ooo_cancel_existing_meetings.prepare_ooo_meeting_cancellations(
            intent_key="ooo-cancel-001",
            event_keys=("person@example.test",),
            schedule=ooo_schedule.OooSchedule(120, 360),
            readiness=_ready(),
        )


def test_out135_remains_reserved_and_not_public() -> None:
    outlook = default_application_registry().get(ApplicationKey.OUTLOOK)
    assert outlook.state is ApplicationState.RESERVED
    assert default_tool_registry().by_application("outlook") == ()
