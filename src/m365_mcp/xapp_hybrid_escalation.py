"""Content-free HYBRID escalation policy for XAPP-014.

The policy selects a bounded execution path from explicit low-cardinality
signals. It does not invoke deterministic tools, agents, models or humans.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class HybridExecutionPath(StrEnum):
    DETERMINISTIC = "DETERMINISTIC"
    AGENTIC_REVIEW = "AGENTIC_REVIEW"
    HUMAN_REVIEW = "HUMAN_REVIEW"


class HybridEscalationReason(StrEnum):
    NONE = "NONE"
    UNSUPPORTED_BRANCH = "UNSUPPORTED_BRANCH"
    AMBIGUOUS_RESULT = "AMBIGUOUS_RESULT"
    MANUAL_INTERVENTION_REQUIRED = "MANUAL_INTERVENTION_REQUIRED"
    POLICY_APPROVAL_REQUIRED = "POLICY_APPROVAL_REQUIRED"


@dataclass(frozen=True)
class HybridEscalationSignal:
    deterministic_supported: bool = True
    ambiguous_result: bool = False
    manual_intervention_required: bool = False
    policy_approval_required: bool = False


@dataclass(frozen=True)
class HybridEscalationDecision:
    path: HybridExecutionPath
    reason: HybridEscalationReason
    execution_performed: bool = False

    def __post_init__(self) -> None:
        if self.execution_performed:
            raise ValueError("HYBRID escalation decision must not execute")
        if self.path is HybridExecutionPath.DETERMINISTIC:
            if self.reason is not HybridEscalationReason.NONE:
                raise ValueError("deterministic path requires NONE escalation reason")
        elif self.reason is HybridEscalationReason.NONE:
            raise ValueError("escalated path requires an explicit reason")


def select_hybrid_escalation(
    signal: HybridEscalationSignal,
) -> HybridEscalationDecision:
    """Choose the narrowest safe path with human review taking precedence."""
    if signal.manual_intervention_required:
        return HybridEscalationDecision(
            HybridExecutionPath.HUMAN_REVIEW,
            HybridEscalationReason.MANUAL_INTERVENTION_REQUIRED,
        )
    if signal.policy_approval_required:
        return HybridEscalationDecision(
            HybridExecutionPath.HUMAN_REVIEW,
            HybridEscalationReason.POLICY_APPROVAL_REQUIRED,
        )
    if signal.ambiguous_result:
        return HybridEscalationDecision(
            HybridExecutionPath.AGENTIC_REVIEW,
            HybridEscalationReason.AMBIGUOUS_RESULT,
        )
    if not signal.deterministic_supported:
        return HybridEscalationDecision(
            HybridExecutionPath.AGENTIC_REVIEW,
            HybridEscalationReason.UNSUPPORTED_BRANCH,
        )
    return HybridEscalationDecision(
        HybridExecutionPath.DETERMINISTIC,
        HybridEscalationReason.NONE,
    )


__all__ = [
    "HybridEscalationDecision",
    "HybridEscalationReason",
    "HybridEscalationSignal",
    "HybridExecutionPath",
    "select_hybrid_escalation",
]
