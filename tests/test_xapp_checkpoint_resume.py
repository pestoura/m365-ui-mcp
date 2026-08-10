from __future__ import annotations

from m365_mcp.application_registry import ApplicationKey
from m365_mcp.execution_lifecycle import (
    ExecutionCheckpoint,
    ExecutionLifecycleState,
)
from m365_mcp.xapp_checkpoint_resume import ResumeState, prepare_checkpoint_resume


def _checkpoint(index: int, state: ExecutionLifecycleState) -> ExecutionCheckpoint:
    return ExecutionCheckpoint(
        saga_id_digest="a" * 64,
        checkpoint_index=index,
        node_id="node-a",
        application=ApplicationKey.PLANNER,
        state=state,
        idempotency_key="b" * 64,
        lock_keys=(),
    )


def test_only_valid_checkpointed_chain_is_marked_resumable() -> None:
    planned = _checkpoint(0, ExecutionLifecycleState.PLANNED)
    active = _checkpoint(1, ExecutionLifecycleState.ACTIVE)
    checkpointed = _checkpoint(2, ExecutionLifecycleState.CHECKPOINTED)
    plan = prepare_checkpoint_resume((planned, active, checkpointed))
    assert plan.state is ResumeState.RESUMABLE
    assert plan.checkpoint_index == 2
    assert plan.next_checkpoint_index == 3
    assert plan.execution_performed is False


def test_active_chain_is_not_inferred_resumable() -> None:
    planned = _checkpoint(0, ExecutionLifecycleState.PLANNED)
    active = _checkpoint(1, ExecutionLifecycleState.ACTIVE)
    plan = prepare_checkpoint_resume((planned, active))
    assert plan.state is ResumeState.NOT_CHECKPOINTED
    assert plan.next_checkpoint_index is None
