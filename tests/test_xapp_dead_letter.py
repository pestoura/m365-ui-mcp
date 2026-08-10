from m365_mcp import xapp_dead_letter

_DIGEST = "a" * 64


def test_dead_letter_record_projects_bounded_manual_state() -> None:
    record = xapp_dead_letter.DeadLetterRecord(
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
    record = xapp_dead_letter.DeadLetterRecord(
        node_id="node-a",
        checkpoint_digest=_DIGEST,
        reason_code="INDETERMINATE_STATE",
        attempt_count=1,
    )

    plan = xapp_dead_letter.prepare_manual_intervention(
        record,
        xapp_dead_letter.ManualInterventionAction.RETRY,
    )

    assert plan.state is xapp_dead_letter.DeadLetterState.RESOLUTION_PREPARED
    assert plan.action is xapp_dead_letter.ManualInterventionAction.RETRY
    assert plan.execution_performed is False
    assert set(xapp_dead_letter.ManualInterventionPlan.__dataclass_fields__) == {
        "node_id",
        "checkpoint_digest",
        "action",
        "state",
        "execution_performed",
    }


def test_manual_intervention_fails_closed_for_non_waiting_record() -> None:
    record = xapp_dead_letter.DeadLetterRecord(
        node_id="node-a",
        checkpoint_digest=_DIGEST,
        reason_code="OPERATOR_REQUIRED",
        attempt_count=2,
        state=xapp_dead_letter.DeadLetterState.CLOSED,
    )

    try:
        xapp_dead_letter.prepare_manual_intervention(
            record,
            xapp_dead_letter.ManualInterventionAction.ABORT,
        )
    except ValueError as exc:
        assert "not waiting" in str(exc)
    else:
        raise AssertionError("expected ValueError for non-waiting dead-letter record")


def test_dead_letter_rejects_unbounded_or_locator_like_input() -> None:
    try:
        xapp_dead_letter.DeadLetterRecord("node-a", _DIGEST, "RETRY_EXHAUSTED", 101)
    except ValueError as exc:
        assert "attempt_count" in str(exc)
    else:
        raise AssertionError("expected ValueError for unbounded attempt count")

    try:
        xapp_dead_letter.DeadLetterRecord(
            "node-a",
            _DIGEST,
            "https://example.invalid",
            1,
        )
    except ValueError as exc:
        assert "semantic token" in str(exc)
    else:
        raise AssertionError("expected ValueError for locator-like reason code")

    try:
        xapp_dead_letter.ManualInterventionPlan(
            node_id="node-a",
            checkpoint_digest=_DIGEST,
            action=xapp_dead_letter.ManualInterventionAction.SKIP,
            execution_performed=True,
        )
    except ValueError as exc:
        assert "must not execute" in str(exc)
    else:
        raise AssertionError("expected ValueError for executed intervention plan")
