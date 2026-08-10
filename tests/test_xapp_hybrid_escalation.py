import pytest

from m365_mcp.xapp_hybrid_escalation import (
    HybridEscalationDecision,
    HybridEscalationReason,
    HybridEscalationSignal,
    HybridExecutionPath,
    select_hybrid_escalation,
)


def test_deterministic_path_is_default_and_non_executing() -> None:
    decision = select_hybrid_escalation(HybridEscalationSignal())

    assert decision.path is HybridExecutionPath.DETERMINISTIC
    assert decision.reason is HybridEscalationReason.NONE
    assert decision.execution_performed is False


def test_ambiguous_or_unsupported_work_escalates_to_agentic_review() -> None:
    ambiguous = select_hybrid_escalation(
        HybridEscalationSignal(ambiguous_result=True)
    )
    unsupported = select_hybrid_escalation(
        HybridEscalationSignal(deterministic_supported=False)
    )

    assert ambiguous == HybridEscalationDecision(
        HybridExecutionPath.AGENTIC_REVIEW,
        HybridEscalationReason.AMBIGUOUS_RESULT,
    )
    assert unsupported.reason is HybridEscalationReason.UNSUPPORTED_BRANCH


def test_human_review_precedes_agentic_escalation() -> None:
    decision = select_hybrid_escalation(
        HybridEscalationSignal(
            deterministic_supported=False,
            ambiguous_result=True,
            manual_intervention_required=True,
            policy_approval_required=True,
        )
    )

    assert decision.path is HybridExecutionPath.HUMAN_REVIEW
    assert decision.reason is HybridEscalationReason.MANUAL_INTERVENTION_REQUIRED
    assert decision.execution_performed is False


def test_decision_invariants_reject_implicit_or_executed_escalation() -> None:
    with pytest.raises(ValueError, match="explicit reason"):
        HybridEscalationDecision(
            HybridExecutionPath.AGENTIC_REVIEW,
            HybridEscalationReason.NONE,
        )

    with pytest.raises(ValueError, match="must not execute"):
        HybridEscalationDecision(
            HybridExecutionPath.HUMAN_REVIEW,
            HybridEscalationReason.POLICY_APPROVAL_REQUIRED,
            execution_performed=True,
        )
