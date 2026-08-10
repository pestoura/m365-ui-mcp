"""Canonical non-executing project/mail follow-up runbook for XAPP-027."""

from __future__ import annotations

from dataclasses import dataclass

from m365_mcp.xapp_runbook_serialization import (
    CanonicalRunbook,
    CanonicalRunbookNode,
    canonical_runbook_digest,
)


@dataclass(frozen=True)
class ProjectMailFollowUpRunbook:
    runbook: CanonicalRunbook
    definition_reference_id: str
    execution_performed: bool = False

    def __post_init__(self) -> None:
        if self.execution_performed:
            raise ValueError("project/mail follow-up runbook must not execute")
        if self.definition_reference_id != canonical_runbook_digest(self.runbook):
            raise ValueError("project/mail follow-up digest does not match runbook")


def build_project_mail_follow_up_runbook(
    *,
    version: str = "1.0.0",
) -> ProjectMailFollowUpRunbook:
    """Build semantic Planner project + synthetic Outlook triage metadata only."""
    runbook = CanonicalRunbook(
        runbook_key="project-mail-follow-up",
        version=version,
        nodes=(
            CanonicalRunbookNode(
                node_id="project-context",
                tool_name="planner_project_snapshot",
            ),
            CanonicalRunbookNode(
                node_id="mail-triage",
                tool_name="xapp_outlook_mail_triage",
            ),
            CanonicalRunbookNode(
                node_id="follow-up-projection",
                tool_name="xapp_project_mail_follow_up_projection",
                depends_on=("mail-triage", "project-context"),
                input_binding_keys=("project-ref", "triage-ref"),
            ),
        ),
    )
    return ProjectMailFollowUpRunbook(
        runbook=runbook,
        definition_reference_id=canonical_runbook_digest(runbook),
    )


__all__ = ["ProjectMailFollowUpRunbook", "build_project_mail_follow_up_runbook"]
