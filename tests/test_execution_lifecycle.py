import m365_mcp.application_registry as application_registry
import m365_mcp.execution_lifecycle as execution_lifecycle
import m365_mcp.state_identity as state_identity
import m365_mcp.typed_locks as typed_locks

IDEMPOTENCY_KEY = "a" * 64
RESULT_DIGEST = "b" * 64


def _planner_identity() -> state_identity.StateIdentity:
    return state_identity.container_state_identity(
        application_registry.ApplicationKey.PLANNER,
        account_scope="professional_session",
        container_kind="plan",
        external_container_id="plan-a",
    )


def _planner_locks() -> tuple[typed_locks.TypedLock, ...]:
    identity = _planner_identity()
    return (
        typed_locks.state_lock("account-a", identity),
        typed_locks.application_lock(
            "account-a",
            application_registry.ApplicationKey.PLANNER,
        ),
        typed_locks.account_lock("account-a"),
    )


def test_checkpoint_binds_cross_app_safe_execution_metadata() -> None:
    identity = _planner_identity()
    checkpoint = execution_lifecycle.start_checkpoint(
        saga_id="saga-a",
        node_id="node-1",
        application=application_registry.ApplicationKey.PLANNER,
        idempotency_key=IDEMPOTENCY_KEY,
        locks=_planner_locks(),
        state_identity=identity,
    )

    assert checkpoint.state is execution_lifecycle.ExecutionLifecycleState.PLANNED
    assert checkpoint.checkpoint_index == 0
    assert checkpoint.application is application_registry.ApplicationKey.PLANNER
    assert checkpoint.state_identity_digest == identity.identity_digest
    assert checkpoint.lock_keys == tuple(
        lock.lock_key for lock in typed_locks.canonical_lock_order(_planner_locks())
    )
    assert len(checkpoint.checkpoint_digest) == 64
    assert "saga-a" not in repr(checkpoint)
    assert "plan-a" not in repr(checkpoint)


def test_checkpoint_transition_chain_is_monotonic_and_valid() -> None:
    planned = execution_lifecycle.start_checkpoint(
        saga_id="saga-a",
        node_id="node-1",
        application=application_registry.ApplicationKey.PLANNER,
        idempotency_key=IDEMPOTENCY_KEY,
        locks=_planner_locks(),
        state_identity=_planner_identity(),
    )
    active = execution_lifecycle.transition_checkpoint(
        planned,
        execution_lifecycle.ExecutionLifecycleState.ACTIVE,
    )
    checkpointed = execution_lifecycle.transition_checkpoint(
        active,
        execution_lifecycle.ExecutionLifecycleState.CHECKPOINTED,
    )
    resumed = execution_lifecycle.transition_checkpoint(
        checkpointed,
        execution_lifecycle.ExecutionLifecycleState.ACTIVE,
    )
    completed = execution_lifecycle.transition_checkpoint(
        resumed,
        execution_lifecycle.ExecutionLifecycleState.COMPLETED,
        result_digest=RESULT_DIGEST,
    )

    chain = (planned, active, checkpointed, resumed, completed)
    execution_lifecycle.validate_checkpoint_chain(chain)
    assert tuple(item.checkpoint_index for item in chain) == (0, 1, 2, 3, 4)
    assert completed.terminal is True
    assert completed.result_digest == RESULT_DIGEST


def test_terminal_checkpoint_cannot_transition() -> None:
    planned = execution_lifecycle.start_checkpoint(
        saga_id="saga-a",
        node_id="node-1",
        application=application_registry.ApplicationKey.PLANNER,
        idempotency_key=IDEMPOTENCY_KEY,
        locks=_planner_locks(),
    )
    failed = execution_lifecycle.transition_checkpoint(
        planned,
        execution_lifecycle.ExecutionLifecycleState.FAILED,
    )

    try:
        execution_lifecycle.transition_checkpoint(
            failed,
            execution_lifecycle.ExecutionLifecycleState.ACTIVE,
        )
    except ValueError as exc:
        assert "invalid lifecycle transition" in str(exc)
    else:
        raise AssertionError("terminal checkpoint transition must fail closed")


def test_completed_checkpoint_requires_result_digest() -> None:
    planned = execution_lifecycle.start_checkpoint(
        saga_id="saga-a",
        node_id="node-1",
        application=application_registry.ApplicationKey.PLANNER,
        idempotency_key=IDEMPOTENCY_KEY,
        locks=_planner_locks(),
    )
    active = execution_lifecycle.transition_checkpoint(
        planned,
        execution_lifecycle.ExecutionLifecycleState.ACTIVE,
    )

    try:
        execution_lifecycle.transition_checkpoint(
            active,
            execution_lifecycle.ExecutionLifecycleState.COMPLETED,
        )
    except ValueError as exc:
        assert "requires result_digest" in str(exc)
    else:
        raise AssertionError("completed checkpoint without result digest must fail")


def test_cross_application_state_or_lock_binding_is_rejected() -> None:
    planner_identity = _planner_identity()
    outlook_lock = typed_locks.application_lock(
        "account-a",
        application_registry.ApplicationKey.OUTLOOK,
    )

    try:
        execution_lifecycle.start_checkpoint(
            saga_id="saga-a",
            node_id="node-1",
            application=application_registry.ApplicationKey.OUTLOOK,
            idempotency_key=IDEMPOTENCY_KEY,
            locks=(),
            state_identity=planner_identity,
        )
    except ValueError as exc:
        assert "state identity application" in str(exc)
    else:
        raise AssertionError("cross-application state identity must fail")

    try:
        execution_lifecycle.start_checkpoint(
            saga_id="saga-a",
            node_id="node-1",
            application=application_registry.ApplicationKey.PLANNER,
            idempotency_key=IDEMPOTENCY_KEY,
            locks=(outlook_lock,),
        )
    except ValueError as exc:
        assert "typed lock application" in str(exc)
    else:
        raise AssertionError("cross-application typed lock must fail")


def test_checkpoint_chain_rejects_binding_changes_and_index_gaps() -> None:
    planned = execution_lifecycle.start_checkpoint(
        saga_id="saga-a",
        node_id="node-1",
        application=application_registry.ApplicationKey.PLANNER,
        idempotency_key=IDEMPOTENCY_KEY,
        locks=_planner_locks(),
    )
    active = execution_lifecycle.transition_checkpoint(
        planned,
        execution_lifecycle.ExecutionLifecycleState.ACTIVE,
    )
    changed = execution_lifecycle.ExecutionCheckpoint(
        saga_id_digest=active.saga_id_digest,
        checkpoint_index=2,
        node_id="node-2",
        application=active.application,
        state=execution_lifecycle.ExecutionLifecycleState.CHECKPOINTED,
        idempotency_key=active.idempotency_key,
        lock_keys=active.lock_keys,
        state_identity_digest=active.state_identity_digest,
    )

    try:
        execution_lifecycle.validate_checkpoint_chain((planned, active, changed))
    except ValueError as exc:
        assert "identity/bindings" in str(exc)
    else:
        raise AssertionError("checkpoint binding changes must fail closed")


def test_planner_checkpoint_placeholders_remain_untouched() -> None:
    import planner_mcp.checkpoints as legacy_checkpoints
    import planner_mcp.sagas as legacy_sagas

    assert legacy_checkpoints.__all__ == []
    assert legacy_sagas.__all__ == []
