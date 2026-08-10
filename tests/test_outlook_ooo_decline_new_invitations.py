from __future__ import annotations

from m365_mcp.application_registry import (
    ApplicationKey,
    ApplicationState,
    default_application_registry,
)
from m365_mcp.apps.outlook import (
    ooo_decline_new_invitations,
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


def test_decline_new_invitation_policy_is_governed_and_non_executable() -> None:
    intent = ooo_decline_new_invitations.prepare_ooo_decline_new_invitations(
        policy_key="ooo-decline-policy",
        schedule=ooo_schedule.OooSchedule(120, 360),
        enabled=True,
        readiness=_ready(),
    )
    projection = intent.to_projection()
    assert intent.executable is False
    assert intent.dispatched is False
    assert projection["approval_required"] is True
    assert projection["live_support_state"] == "UNOBSERVED"


def test_out134_remains_reserved_and_not_public() -> None:
    outlook = default_application_registry().get(ApplicationKey.OUTLOOK)
    assert outlook.state is ApplicationState.RESERVED
    assert default_tool_registry().by_application("outlook") == ()
