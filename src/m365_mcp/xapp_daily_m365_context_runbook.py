"""Canonical non-executing daily M365 context runbook for XAPP-028."""

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

    def __post_init__(self) -> None:
        if self.execution_performed:
            raise ValueError("daily M365 context runbook must not execute")
        if self.definition_reference_id != canonical_runbook_digest(self.runbook):
            raise ValueError("daily M365 context digest does not match runbook")


def build_daily_m365_context_runbook(*, version: str = "1.0.0") -> DailyM365ContextRunbook:
    """Build semantic Planner + synthetic Outlook daily-context metadata only."""
    runbook = CanonicalRunbook(
        runbook_key="daily-m365-context",
        version=version,
        nodes=(
            CanonicalRunbookNode(
                node_id="project-context",
                tool_name="planner_project_snapshot",
            ),
            CanonicalRunbookNode(
                node_id="inbox-digest",
                tool_name="xapp_outlook_inbox_digest",
            ),
            CanonicalRunbookNode(
                node_id="daily-work-context",
                tool_name="xapp_outlook_daily_work_context",
                depends_on=("inbox-digest",),
            ),
            CanonicalRunbookNode(
                node_id="daily-context-projection",
                tool_name="xapp_daily_m365_context_projection",
                depends_on=(
                    "daily-work-context",
                    "project-context",
                ),
                input_binding_keys=("project-ref", "digest-ref", "work-ref"),
            ),
        ),
    )
    return DailyM365ContextRunbook(
        runbook=runbook,
        definition_reference_id=canonical_runbook_digest(runbook),
    )


__all__ = ["DailyM365ContextRunbook", "build_daily_m365_context_runbook"]
