from __future__ import annotations

import pytest

from m365_mcp.application_registry import (
    ApplicationKey,
    ApplicationState,
    default_application_registry,
)
from m365_mcp.apps.outlook import meeting_new_time_proposals, readiness
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


def _proposal() -> meeting_new_time_proposals.SyntheticNewTimeProposal:
    return meeting_new_time_proposals.SyntheticNewTimeProposal(
        meeting_key="meeting-001",
        start_day_offset=3,
        start_minute_of_day=660,
        duration_minutes=45,
    )


def test_new_time_proposal_requires_prepare_allowance_and_never_sends() -> None:
    with pytest.raises(PermissionError, match="outbound-prepare"):
        meeting_new_time_proposals.prepare_new_time_proposal(
            (), _proposal(), readiness=_ready()
        )

    proposals, result = meeting_new_time_proposals.prepare_new_time_proposal(
        (),
        _proposal(),
        readiness=_ready(),
        allow_outbound_prepare=True,
    )
    assert proposals == (_proposal(),)
    assert result.proposal_sent is False
    assert result.verified is True


def test_new_time_proposal_is_bounded_and_idempotent() -> None:
    with pytest.raises(ValueError, match="within a day"):
        meeting_new_time_proposals.SyntheticNewTimeProposal(
            meeting_key="meeting-001",
            start_day_offset=1,
            start_minute_of_day=1440,
            duration_minutes=30,
        )

    proposals, _ = meeting_new_time_proposals.prepare_new_time_proposal(
        (), _proposal(), readiness=_ready(), allow_outbound_prepare=True
    )
    proposals, result = meeting_new_time_proposals.prepare_new_time_proposal(
        proposals,
        _proposal(),
        readiness=_ready(),
        allow_outbound_prepare=True,
    )
    assert result.changed is False
    assert proposals == (_proposal(),)


def test_out088_remains_reserved_and_not_public() -> None:
    outlook = default_application_registry().get(ApplicationKey.OUTLOOK)
    assert outlook.state is ApplicationState.RESERVED
    assert default_tool_registry().by_application("outlook") == ()
