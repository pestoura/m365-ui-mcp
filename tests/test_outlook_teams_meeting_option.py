from __future__ import annotations

from m365_mcp.application_registry import (
    ApplicationKey,
    ApplicationState,
    default_application_registry,
)
from m365_mcp.apps.outlook import readiness, teams_meeting_option
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


def test_teams_option_has_readback_without_join_url_generation() -> None:
    desired = teams_meeting_option.SyntheticTeamsMeetingOption(
        meeting_key="meeting-001",
        enabled=True,
    )
    options, result = teams_meeting_option.set_teams_meeting_option(
        (), desired, readiness=_ready()
    )
    assert options == (desired,)
    assert result.enabled is True
    assert result.verified is True
    assert result.join_url_generated is False
    assert "http" not in str(desired.to_payload()).lower()


def test_teams_option_is_idempotent() -> None:
    desired = teams_meeting_option.SyntheticTeamsMeetingOption(
        meeting_key="meeting-001",
        enabled=False,
    )
    options, _ = teams_meeting_option.set_teams_meeting_option(
        (), desired, readiness=_ready()
    )
    options, result = teams_meeting_option.set_teams_meeting_option(
        options, desired, readiness=_ready()
    )
    assert result.changed is False
    assert options == (desired,)


def test_out083_remains_reserved_and_not_public() -> None:
    outlook = default_application_registry().get(ApplicationKey.OUTLOOK)
    assert outlook.state is ApplicationState.RESERVED
    assert default_tool_registry().by_application("outlook") == ()
