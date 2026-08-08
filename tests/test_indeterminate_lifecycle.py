import pytest

import m365_mcp.application_registry as application_registry
import m365_mcp.execution_lifecycle as execution_lifecycle

IDEMPOTENCY_KEY = "a" * 64


def _planned() -> execution_lifecycle.ExecutionCheckpoint:
    return execution_lifecycle.start_checkpoint(
        saga_id="saga-a",
        node_id="node-1",
        application=application_registry.ApplicationKey.PLANNER,
        idempotency_key=IDEMPOTENCY_KEY,
        locks=(),
    )


def test_indeterminate_is_terminal_and_requires_reason_code() -> None:
    active = execution_lifecycle.transition_checkpoint(
        _planned(),
        execution_lifecycle.ExecutionLifecycleState.ACTIVE,
    )
    indeterminate = execution_lifecycle.transition_checkpoint(
        active,
        execution_lifecycle.ExecutionLifecycleState.INDETERMINATE,
        uncertainty_code="READ_BACK_AMBIGUOUS",
    )

    assert indeterminate.terminal is True
    assert indeterminate.result_digest is None
    assert indeterminate.uncertainty_code == "READ_BACK_AMBIGUOUS"

    with pytest.raises(ValueError, match="invalid lifecycle transition"):
        execution_lifecycle.transition_checkpoint(
            indeterminate,
            execution_lifecycle.ExecutionLifecycleState.ACTIVE,
        )


def test_indeterminate_cannot_be_entered_before_execution_starts() -> None:
    with pytest.raises(ValueError, match="invalid lifecycle transition"):
        execution_lifecycle.transition_checkpoint(
            _planned(),
            execution_lifecycle.ExecutionLifecycleState.INDETERMINATE,
            uncertainty_code="NO_EFFECT_EVIDENCE",
        )


def test_indeterminate_requires_semantic_uncertainty_code() -> None:
    active = execution_lifecycle.transition_checkpoint(
        _planned(),
        execution_lifecycle.ExecutionLifecycleState.ACTIVE,
    )

    with pytest.raises(ValueError, match="requires uncertainty_code"):
        execution_lifecycle.transition_checkpoint(
            active,
            execution_lifecycle.ExecutionLifecycleState.INDETERMINATE,
        )

    with pytest.raises(ValueError, match="uncertainty_code"):
        execution_lifecycle.transition_checkpoint(
            active,
            execution_lifecycle.ExecutionLifecycleState.INDETERMINATE,
            uncertainty_code="ambiguous state",
        )


def test_only_indeterminate_state_may_carry_uncertainty_code() -> None:
    active = execution_lifecycle.transition_checkpoint(
        _planned(),
        execution_lifecycle.ExecutionLifecycleState.ACTIVE,
    )

    with pytest.raises(ValueError, match="only indeterminate checkpoint"):
        execution_lifecycle.transition_checkpoint(
            active,
            execution_lifecycle.ExecutionLifecycleState.FAILED,
            uncertainty_code="UNEXPECTED",
        )


def test_indeterminate_cannot_carry_success_result_digest() -> None:
    active = execution_lifecycle.transition_checkpoint(
        _planned(),
        execution_lifecycle.ExecutionLifecycleState.ACTIVE,
    )

    with pytest.raises(ValueError, match="only completed checkpoint"):
        execution_lifecycle.transition_checkpoint(
            active,
            execution_lifecycle.ExecutionLifecycleState.INDETERMINATE,
            result_digest="b" * 64,
            uncertainty_code="READ_BACK_AMBIGUOUS",
        )


def test_checkpoint_chain_accepts_indeterminate_terminal() -> None:
    planned = _planned()
    active = execution_lifecycle.transition_checkpoint(
        planned,
        execution_lifecycle.ExecutionLifecycleState.ACTIVE,
    )
    checkpointed = execution_lifecycle.transition_checkpoint(
        active,
        execution_lifecycle.ExecutionLifecycleState.CHECKPOINTED,
    )
    indeterminate = execution_lifecycle.transition_checkpoint(
        checkpointed,
        execution_lifecycle.ExecutionLifecycleState.INDETERMINATE,
        uncertainty_code="READ_BACK_NOT_PROVABLE",
    )

    execution_lifecycle.validate_checkpoint_chain(
        (planned, active, checkpointed, indeterminate)
    )
    assert len(indeterminate.checkpoint_digest) == 64
