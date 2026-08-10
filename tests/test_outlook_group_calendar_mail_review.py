from __future__ import annotations

from m365_mcp.application_registry import (
    ApplicationKey,
    ApplicationState,
    default_application_registry,
)
from m365_mcp.apps.outlook import (
    group_calendar_mail_review,
    m365_group_reads,
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


def test_group_review_is_read_only_and_has_no_generic_executor() -> None:
    group = m365_group_reads.default_synthetic_groups()[0]
    review = group_calendar_mail_review.review_group_calendar_mail_interactions(
        group,
        readiness=_ready(),
    )
    projection = review.to_projection()
    assert (
        review.calendar_status
        is group_calendar_mail_review.GroupSurfaceStatus.READ_ONLY_SYNTHETIC
    )
    assert review.mail_status is group_calendar_mail_review.GroupSurfaceStatus.READ_ONLY_SYNTHETIC
    assert projection["membership_mutation_available"] is False
    assert projection["generic_executor_available"] is False
    assert projection["live_support_state"] == "UNOBSERVED"


def test_out138_remains_reserved_and_not_public() -> None:
    outlook = default_application_registry().get(ApplicationKey.OUTLOOK)
    assert outlook.state is ApplicationState.RESERVED
    assert default_tool_registry().by_application("outlook") == ()
