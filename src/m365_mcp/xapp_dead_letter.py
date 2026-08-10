"""Dead-letter and manual-intervention state for XAPP-010.

Only bounded reason codes, checkpoint digests and prepared operator decisions are
modeled. Raw exceptions are not retained and retry/skip/abort are never executed
by this module.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

_MAX_ATTEMPTS = 100


class DeadLetterState(StrEnum):
    WAITING_MANUAL = "WAITING_MANUAL"
    RESOLUTION_PREPARED = "RESOLUTION_PREPARED"
    CLOSED = "CLOSED"


class ManualInterventionAction(StrEnum):
    RETRY = "RETRY"
    SKIP = "SKIP"
    ABORT = "ABORT"


def _token(field: str, value: str) -> None:
    invalid = (
        not value
        or value != value.strip()
        or any(char.isspace() for char in value)
        or "://" in value
    )
    if invalid:
        raise ValueError(f"{field} must be a non-empty semantic token")


def _digest(value: str) -> None:
    if len(value) != 64 or any(char not in "0123456789abcdef" for char in value):
        raise ValueError("checkpoint_digest must be lowercase SHA-256 hex")


@dataclass(frozen=True)
class DeadLetterRecord:
    node_id: str
    checkpoint_digest: str
    reason_code: str
    attempt_count: int
    state: DeadLetterState = DeadLetterState.WAITING_MANUAL

    def __post_init__(self) -> None:
        _token("node_id", self.node_id)
        _digest(self.checkpoint_digest)
        _token("reason_code", self.reason_code)
        if not 1 <= self.attempt_count <= _MAX_ATTEMPTS:
            raise ValueError("attempt_count must be between 1 and 100")

    def to_projection(self) -> dict[str, object]:
        return {
            "node_id": self.node_id,
            "checkpoint_digest": self.checkpoint_digest,
            "reason_code": self.reason_code,
            "attempt_count": self.attempt_count,
            "state": self.state.value,
        }


@dataclass(frozen=True)
class ManualInterventionPlan:
    node_id: str
    checkpoint_digest: str
    action: ManualInterventionAction
    state: DeadLetterState = DeadLetterState.RESOLUTION_PREPARED
    execution_performed: bool = False

    def __post_init__(self) -> None:
        _token("node_id", self.node_id)
        _digest(self.checkpoint_digest)
        if self.execution_performed:
            raise ValueError("manual-intervention plan must not execute an action")


def prepare_manual_intervention(
    record: DeadLetterRecord,
    action: ManualInterventionAction,
) -> ManualInterventionPlan:
    """Prepare one operator disposition without executing retry, skip or abort."""
    if record.state is not DeadLetterState.WAITING_MANUAL:
        raise ValueError("dead-letter record is not waiting for manual intervention")
    return ManualInterventionPlan(
        node_id=record.node_id,
        checkpoint_digest=record.checkpoint_digest,
        action=action,
    )


__all__ = [
    "DeadLetterRecord",
    "DeadLetterState",
    "ManualInterventionAction",
    "ManualInterventionPlan",
    "prepare_manual_intervention",
]
