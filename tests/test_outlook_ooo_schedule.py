from __future__ import annotations

import pytest

from m365_mcp.application_registry import (
    ApplicationKey,
    ApplicationState,
    default_application_registry,
)
from m365_mcp.apps.outlook import ooo_schedule, readiness
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


def test_ooo_schedule_uses_relative_slots_and_read_back() -> None:
    current = ooo_schedule.OooSchedule(0, 60)
    desired = ooo_schedule.OooSchedule(120, 360)
    updated, result = ooo_schedule.configure_ooo_schedule(
        current,
        desired,
        readiness=_ready(),
    )
    assert updated == desired
    assert updated.anchor == "SYNTHETIC_WEEK"
    assert result.changed is True
    assert result.verified is True
    assert result.dispatched is False


def test_ooo_schedule_rejects_real_or_unbounded_shape() -> None:
    with pytest.raises(ValueError, match="15-minute"):
        ooo_schedule.OooSchedule(1, 60)
    with pytest.raises(ValueError, match="real timestamp"):
        ooo_schedule.OooSchedule(0, 60, anchor="2026-08-10T09:00:00Z")


def test_out132_remains_reserved_and_not_public() -> None:
    outlook = default_application_registry().get(ApplicationKey.OUTLOOK)
    assert outlook.state is ApplicationState.RESERVED
    assert default_tool_registry().by_application("outlook") == ()
