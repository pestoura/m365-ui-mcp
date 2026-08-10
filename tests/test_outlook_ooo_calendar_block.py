from __future__ import annotations

from m365_mcp.application_registry import (
    ApplicationKey,
    ApplicationState,
    default_application_registry,
)
from m365_mcp.apps.outlook import ooo_calendar_block, ooo_schedule, readiness
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


def test_ooo_calendar_block_has_exact_local_read_back() -> None:
    desired = ooo_calendar_block.OooCalendarBlock(
        "ooo-block-001",
        "calendar-primary",
        ooo_schedule.OooSchedule(120, 360),
    )
    blocks, result = ooo_calendar_block.configure_ooo_calendar_block(
        (), desired, readiness=_ready()
    )
    assert blocks == (desired,)
    assert result.read_back == desired
    assert result.changed is True
    assert result.verified is True
    assert result.dispatched is False

    same, again = ooo_calendar_block.configure_ooo_calendar_block(
        blocks, desired, readiness=_ready()
    )
    assert same == blocks
    assert again.changed is False


def test_out133_remains_reserved_and_not_public() -> None:
    outlook = default_application_registry().get(ApplicationKey.OUTLOOK)
    assert outlook.state is ApplicationState.RESERVED
    assert default_tool_registry().by_application("outlook") == ()
