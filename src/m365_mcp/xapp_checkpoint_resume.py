"""Long-run checkpoint/resume planning for XAPP-009.

The module reuses CORE-040/042 checkpoint-chain validation and exposes only a
resume disposition. It neither persists checkpoints nor resumes execution.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from m365_mcp.execution_lifecycle import (
    ExecutionCheckpoint,
    ExecutionLifecycleState,
    validate_checkpoint_chain,
)


class ResumeState(StrEnum):
    RESUMABLE = "RESUMABLE"
    TERMINAL = "TERMINAL"
    NOT_CHECKPOINTED = "NOT_CHECKPOINTED"


@dataclass(frozen=True)
class ResumePlan:
    state: ResumeState
    node_id: str
    checkpoint_index: int
    checkpoint_digest: str
    next_checkpoint_index: int | None
    execution_performed: bool = False

    def __post_init__(self) -> None:
        if self.checkpoint_index < 0:
            raise ValueError("checkpoint_index must be non-negative")
        if self.next_checkpoint_index is not None:
            if self.next_checkpoint_index != self.checkpoint_index + 1:
                raise ValueError("next checkpoint index must advance exactly once")
        if self.execution_performed:
            raise ValueError("resume planner must not execute work")


def prepare_checkpoint_resume(
    checkpoints: tuple[ExecutionCheckpoint, ...],
) -> ResumePlan:
    """Validate one chain and describe whether its latest checkpoint can resume."""
    validate_checkpoint_chain(checkpoints)
    latest = checkpoints[-1]
    if latest.state is ExecutionLifecycleState.CHECKPOINTED:
        state = ResumeState.RESUMABLE
        next_index: int | None = latest.checkpoint_index + 1
    elif latest.terminal:
        state = ResumeState.TERMINAL
        next_index = None
    else:
        state = ResumeState.NOT_CHECKPOINTED
        next_index = None
    return ResumePlan(
        state=state,
        node_id=latest.node_id,
        checkpoint_index=latest.checkpoint_index,
        checkpoint_digest=latest.checkpoint_digest,
        next_checkpoint_index=next_index,
    )


__all__ = ["ResumePlan", "ResumeState", "prepare_checkpoint_resume"]
