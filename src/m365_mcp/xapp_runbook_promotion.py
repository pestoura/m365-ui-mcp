"""Fail-closed immutable runbook promotion planning for XAPP-013.

Promotion validates canonical definition identity and lifecycle transitions, but
never mutates a registry or executes a runbook.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import StrEnum

from m365_mcp.xapp_runbook_registry import RunbookLifecycle, RunbookRegistration


class RunbookPromotionAction(StrEnum):
    PUBLISH = "PUBLISH"
    RETIRE = "RETIRE"


@dataclass(frozen=True)
class RunbookPromotionPlan:
    before: RunbookRegistration
    after: RunbookRegistration
    action: RunbookPromotionAction
    execution_performed: bool = False

    def __post_init__(self) -> None:
        if self.execution_performed:
            raise ValueError("runbook promotion plan must not execute")
        if self.before.registry_key != self.after.registry_key:
            raise ValueError("runbook promotion cannot change key/version identity")
        if self.before.definition_reference_id != self.after.definition_reference_id:
            raise ValueError("runbook promotion cannot change definition identity")


def prepare_runbook_promotion(
    registration: RunbookRegistration,
    action: RunbookPromotionAction,
    *,
    canonical_definition_digest: str,
) -> RunbookPromotionPlan:
    """Prepare one validated lifecycle transition without mutating a registry."""
    if canonical_definition_digest != registration.definition_reference_id:
        raise ValueError("runbook canonical definition digest does not match registry")

    transitions = {
        (RunbookLifecycle.DRAFT, RunbookPromotionAction.PUBLISH): RunbookLifecycle.PUBLISHED,
        (RunbookLifecycle.PUBLISHED, RunbookPromotionAction.RETIRE): RunbookLifecycle.RETIRED,
    }
    target = transitions.get((registration.lifecycle, action))
    if target is None:
        raise ValueError("runbook promotion lifecycle transition is not allowed")

    return RunbookPromotionPlan(
        before=registration,
        after=replace(registration, lifecycle=target),
        action=action,
    )


__all__ = [
    "RunbookPromotionAction",
    "RunbookPromotionPlan",
    "prepare_runbook_promotion",
]
