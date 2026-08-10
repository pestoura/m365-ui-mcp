from __future__ import annotations

import pytest

from m365_mcp.application_registry import (
    ApplicationKey,
    ApplicationState,
    default_application_registry,
)
from m365_mcp.apps.outlook import m365_group_reads, readiness
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


def test_group_discovery_and_get_are_identity_free_reads() -> None:
    groups = m365_group_reads.default_synthetic_groups()
    listed = m365_group_reads.list_synthetic_groups(groups, readiness=_ready())
    assert tuple(item.group_key for item in listed) == ("group-alpha", "group-beta")
    group = m365_group_reads.get_synthetic_group(
        groups, "group-alpha", readiness=_ready()
    )
    projection = group.to_projection()
    assert projection["calendar_available"] is True
    assert projection["mailbox_available"] is True
    assert projection["membership_governance_state"] == "OUT_OF_SCOPE"
    assert projection["live_support_state"] == "UNOBSERVED"


def test_group_key_rejects_address_shape() -> None:
    with pytest.raises(ValueError, match="address or URL"):
        m365_group_reads.SyntheticM365Group(
            "group@example.test",
            "Synthetic Group",
            True,
            True,
        )


def test_out137_remains_reserved_and_not_public() -> None:
    outlook = default_application_registry().get(ApplicationKey.OUTLOOK)
    assert outlook.state is ApplicationState.RESERVED
    assert default_tool_registry().by_application("outlook") == ()
