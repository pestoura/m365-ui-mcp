"""Canonical non-executing Daily M365 context runbook for XAPP-028.

The runbook links Planner project context with the previously validated
synthetic Outlook daily-work context. It contains semantic metadata only and
never executes Planner, Outlook, browser, or tenant operations.
"""

from __future__ import annotations

from dataclasses import dataclass

from m365_mcp.xapp_runbook_serialization import (
    CanonicalRunbook,
    CanonicalRunbookNode,
    canonical_runbook_digest,
)


@dataclass(frozen=True)
class DailyM365ContextRunbook:
    runbook: CanonicalRunbook
    definition_reference_id: str
    execution_performed: bool = False
    outlook_live_observed: bool = False

    def __post_init__(self) -> None:
        if self.execution_performed:
            raise ValueError("Daily M365 context runbook must not execute")
        if self.outlook_live_observed:
            raise ValueError("Daily M365 context runbook must not claim Outlook LIVE support")
        if self.definition_reference_id != canonical_runbook_digest(self.runbook):
            raise ValueError("Daily M365 context digest does not match runbook")


def build_daily_m365_context_runbook(
    *,
    version: str = "1.0.0",
) -> DailyM365ContextRunbook:
    """Build deterministic Planner + synthetic Outlook daily-context metadata."""
    runbook = CanonicalRunbook(
        runbook_key="daily-m365-context",
        version=version,
        nodes=(
            CanonicalRunbookNode(
                node_id="planner-context",
                tool_name="planner_project_snapshot",
            ),
            CanonicalRunbookNode(
                node_id="outlook-context",
                tool_name="xapp_outlook_daily_work_context",
            ),
            CanonicalRunbookNode(
                node_id="daily-context",
                tool_name="xapp_daily_m365_context_projection",
                depends_on=("outlook-context", "planner-context"),
                input_binding_keys=("outlook-context-ref", "planner-context-ref"),
            ),
        ),
    )
    return DailyM365ContextRunbook(
        runbook=runbook,
        definition_reference_id=canonical_runbook_digest(runbook),
    )


__all__ = ["DailyM365ContextRunbook", "build_daily_m365_context_runbook"]
