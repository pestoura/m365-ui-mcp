from __future__ import annotations

import pytest

from m365_mcp.application_registry import (
    ApplicationKey,
    ApplicationState,
    default_application_registry,
)
from m365_mcp.apps.outlook import readiness, rule_reads
from m365_mcp.tool_registry import default_tool_registry

# Cumulative revalidation trigger: OUT-060 integrated in Wave G.


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


def test_rule_list_and_get_are_bounded_and_ordered() -> None:
    listing = rule_reads.list_rules(readiness=_ready())
    assert listing.rule_count == 2
    assert tuple(rule.order for rule in listing.rules) == (1, 2)
    assert listing.enabled_count == 2
    selected = rule_reads.get_rule("rule-project", readiness=_ready())
    assert selected.display_name == "Synthetic project routing"
    assert selected.synthetic is True


def test_unknown_rule_fails_closed() -> None:
    with pytest.raises(ValueError, match="exactly one"):
        rule_reads.get_rule("rule-missing", readiness=_ready())


def test_out061_remains_reserved_and_not_public() -> None:
    outlook = default_application_registry().get(ApplicationKey.OUTLOOK)
    assert outlook.state is ApplicationState.RESERVED
    assert default_tool_registry().by_application("outlook") == ()
