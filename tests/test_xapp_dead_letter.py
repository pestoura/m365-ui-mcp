import pytest

from m365_mcp import xapp_dead_letter as dead_letter


_DIGEST = "a" * 64


def test_dead_letter_record_projects_bounded_manual_state() -> None:
    record = dead_letter.DeadLetterRecord(
        node_id="node-a",
        checkpoint_digest=_DIGEST,
        reason_code="RETRY_EXHAUSTED",
        attempt_count=3,
    )

    assert record.to_projection() == {
        "node_id": "node-a",
        "checkpoint_digest": _DIGEST,
        "reason_code": "RETRY_EXHAUSTED",
        "attempt_count": 3,
        "state": "WAITING_MANUAL",
    }


def test_prepare_manual_intervention_never_executes_action() -> None:
    record = dead_letter.DeadLetterRecord(
        node_id="node-a",
        checkpoint_digest=_DIGEST,
        reason_code="INDETERMINATE_STATE",
        attempt_count=1,
    )

    plan = dead_letter.prepare_manual_intervention(
        record,
        dead_letter.ManualInterventionAction.RETRY,
    )

    assert plan.state is dead_letter.DeadLetterState.RESOLUTION_PREPARED
    assert plan.action is dead_letter.ManualInterventionAction.RETRY
    assert plan.execution_performed is False
    assert set(dead_letter.ManualInterventionPlan.__dataclass_fields__) == {
        "node_id",
        "checkpoint_digest",
        "action",
        "state",
        "execution_performed",
    }


def test_manual_intervention_fails_closed_for_non_waiting_record() -> None:
    record = dead_letter.DeadLetterRecord(
        node_id="node-a",
        checkpoint_digest=_DIGEST,
        reason_code="OPERATOR_REQUIRED",
        attempt_count=2,
        state=dead_letter.DeadLetterState.CLOSED,
    )

    with pytest.raises(ValueError, match="not waiting"):
        dead_letter.prepare_manual_intervention(
            record,
            dead_letter.ManualInterventionAction.ABORT,
        )


def test_dead_letter_rejects_unbounded_or_locator_like_input() -> None:
    with pytest.raises(ValueError, match="attempt_count"):
        dead_letter.DeadLetterRecord("node-a", _DIGEST, "RETRY_EXHAUSTED", 101)

    with pytest.raises(ValueError, match="semantic token"):
        dead_letter.DeadLetterRecord(
            "node-a",
            _DIGEST,
            "https://example.invalid",
            1,
        )

    with pytest.raises(ValueError, match="must not execute"):
        dead_letter.ManualInterventionPlan(
            node_id="node-a",
            checkpoint_digest=_DIGEST,
            action=dead_letter.ManualInterventionAction.SKIP,
            execution_performed=True,
        )
