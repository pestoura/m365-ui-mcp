"""Canonical non-executing meeting-preparation runbook for XAPP-026."""

from __future__ import annotations

from dataclasses import dataclass

from m365_mcp.xapp_runbook_serialization import (
    CanonicalRunbook,
    CanonicalRunbookNode,
    canonical_runbook_digest,
)


@dataclass(frozen=True)
class MeetingPreparationRunbook:
    runbook: CanonicalRunbook
    definition_reference_id: str
    execution_performed: bool = False

    def __post_init__(self) -> None:
        if self.execution_performed:
            raise ValueError("meeting-preparation runbook must not execute")
        if self.definition_reference_id != canonical_runbook_digest(self.runbook):
            raise ValueError("meeting-preparation digest does not match runbook")


def build_meeting_preparation_runbook(*, version: str = "1.0.0") -> MeetingPreparationRunbook:
    """Build semantic Planner/Outlook preparation metadata only."""
    runbook = CanonicalRunbook(
        runbook_key="meeting-preparation",
        version=version,
        nodes=(
            CanonicalRunbookNode(
                node_id="project-context",
                tool_name="planner_project_snapshot",
            ),
            CanonicalRunbookNode(
                node_id="person-context",
                tool_name="xapp_outlook_person_context",
            ),
            CanonicalRunbookNode(
                node_id="daily-work-context",
                tool_name="xapp_outlook_daily_work_context",
                depends_on=("person-context",),
            ),
            CanonicalRunbookNode(
                node_id="meeting-brief",
                tool_name="xapp_meeting_preparation_projection",
                depends_on=(
                    "daily-work-context",
                    "project-context",
                ),
                input_binding_keys=("project-ref", "person-ref", "work-ref"),
            ),
        ),
    )
    return MeetingPreparationRunbook(
        runbook=runbook,
        definition_reference_id=canonical_runbook_digest(runbook),
    )


__all__ = ["MeetingPreparationRunbook", "build_meeting_preparation_runbook"]
