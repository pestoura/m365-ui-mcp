from __future__ import annotations

import pytest

from m365_mcp.application_registry import (
    ApplicationKey,
    ApplicationState,
    default_application_registry,
)
from m365_mcp.apps.outlook import quick_step_reads, readiness
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


def test_quick_step_list_and_get_are_bounded_and_ordered() -> None:
    listing = quick_step_reads.list_quick_steps(readiness=_ready())
    assert listing.quick_step_count == 2
    assert tuple(step.order for step in listing.steps) == (1, 2)
    assert listing.destructive_count == 0
    assert listing.outbound_count == 0

    selected = quick_step_reads.get_quick_step(
        "quick-archive-read",
        readiness=_ready(),
    )
    assert selected.step.display_name == "Synthetic archive and read"
    assert len(selected.step.actions) == 2
    assert selected.synthetic is True


def test_unknown_quick_step_fails_closed() -> None:
    with pytest.raises(ValueError, match="exactly one"):
        quick_step_reads.get_quick_step("quick-missing", readiness=_ready())


def test_out065_remains_reserved_and_not_public() -> None:
    outlook = default_application_registry().get(ApplicationKey.OUTLOOK)
    assert outlook.state is ApplicationState.RESERVED
    assert default_tool_registry().by_application("outlook") == ()
