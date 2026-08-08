"""Cross-application saga/checkpoint lifecycle for CORE-040/CORE-042.

The lifecycle binds checkpoints to semantic application/node identity,
CORE-037 state identity, CORE-038 idempotency keys and CORE-039 lock keys.
Only digests and bounded metadata are projected; tenant content is not stored.
CORE-042 adds INDETERMINATE for mutations whose resulting Microsoft state
cannot be proven. Compensation strategy remains owned by CORE-041.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, replace
from enum import StrEnum

from m365_mcp.application_registry import ApplicationKey
from m365_mcp.state_identity import StateIdentity
from m365_mcp.typed_locks import TypedLock, canonical_lock_order


class ExecutionLifecycleState(StrEnum):
    """Closed cross-application execution lifecycle states."""

    PLANNED = "PLANNED"
    ACTIVE = "ACTIVE"
    CHECKPOINTED = "CHECKPOINTED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    INDETERMINATE = "INDETERMINATE"


_TERMINAL_STATES = frozenset(
    {
        ExecutionLifecycleState.COMPLETED,
        ExecutionLifecycleState.FAILED,
        ExecutionLifecycleState.INDETERMINATE,
    }
)

_ALLOWED_TRANSITIONS: dict[ExecutionLifecycleState, frozenset[ExecutionLifecycleState]] = {
    ExecutionLifecycleState.PLANNED: frozenset(
        {
            ExecutionLifecycleState.ACTIVE,
            ExecutionLifecycleState.FAILED,
        }
    ),
    ExecutionLifecycleState.ACTIVE: frozenset(
        {
            ExecutionLifecycleState.CHECKPOINTED,
            ExecutionLifecycleState.COMPLETED,
            ExecutionLifecycleState.FAILED,
            ExecutionLifecycleState.INDETERMINATE,
        }
    ),
    ExecutionLifecycleState.CHECKPOINTED: frozenset(
        {
            ExecutionLifecycleState.ACTIVE,
            ExecutionLifecycleState.CHECKPOINTED,
            ExecutionLifecycleState.COMPLETED,
            ExecutionLifecycleState.FAILED,
            ExecutionLifecycleState.INDETERMINATE,
        }
    ),
    ExecutionLifecycleState.COMPLETED: frozenset(),
    ExecutionLifecycleState.FAILED: frozenset(),
    ExecutionLifecycleState.INDETERMINATE: frozenset(),
}


def _opaque_digest(value: str, *, field_name: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{field_name} must not be empty")
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _validate_digest(value: str, *, field_name: str) -> None:
    if len(value) != 64 or any(char not in "0123456789abcdef" for char in value):
        raise ValueError(f"{field_name} must be lowercase SHA-256 hex")


def _semantic_token(value: str, *, field_name: str) -> str:
    normalized = value.strip()
    if not normalized or any(char.isspace() for char in normalized):
        raise ValueError(f"{field_name} must be a non-empty semantic token")
    return normalized


@dataclass(frozen=True)
class ExecutionCheckpoint:
    """Immutable cross-application checkpoint for one semantic node."""

    saga_id_digest: str
    checkpoint_index: int
    node_id: str
    application: ApplicationKey
    state: ExecutionLifecycleState
    idempotency_key: str
    lock_keys: tuple[str, ...]
    state_identity_digest: str | None = None
    result_digest: str | None = None
    uncertainty_code: str | None = None

    def __post_init__(self) -> None:
        _validate_digest(self.saga_id_digest, field_name="saga_id_digest")
        if self.checkpoint_index < 0:
            raise ValueError("checkpoint_index must be non-negative")
        _semantic_token(self.node_id, field_name="node_id")
        _validate_digest(self.idempotency_key, field_name="idempotency_key")
        for lock_key in self.lock_keys:
            _validate_digest(lock_key, field_name="lock_key")
        if len(set(self.lock_keys)) != len(self.lock_keys):
            raise ValueError("lock_keys must be unique")
        if self.state_identity_digest is not None:
            _validate_digest(
                self.state_identity_digest,
                field_name="state_identity_digest",
            )
        if self.result_digest is not None:
            _validate_digest(self.result_digest, field_name="result_digest")
        if self.state is ExecutionLifecycleState.COMPLETED:
            if self.result_digest is None:
                raise ValueError("completed checkpoint requires result_digest")
        elif self.result_digest is not None:
            raise ValueError("only completed checkpoint may carry result_digest")

        if self.state is ExecutionLifecycleState.INDETERMINATE:
            if self.uncertainty_code is None:
                raise ValueError("indeterminate checkpoint requires uncertainty_code")
            _semantic_token(self.uncertainty_code, field_name="uncertainty_code")
        elif self.uncertainty_code is not None:
            raise ValueError("only indeterminate checkpoint may carry uncertainty_code")

    @property
    def terminal(self) -> bool:
        return self.state in _TERMINAL_STATES

    @property
    def checkpoint_digest(self) -> str:
        payload: dict[str, object] = {
            "saga_id_digest": self.saga_id_digest,
            "checkpoint_index": self.checkpoint_index,
            "node_id": self.node_id,
            "application": self.application.value,
            "state": self.state.value,
            "idempotency_key": self.idempotency_key,
            "lock_keys": list(self.lock_keys),
        }
        if self.state_identity_digest is not None:
            payload["state_identity_digest"] = self.state_identity_digest
        if self.result_digest is not None:
            payload["result_digest"] = self.result_digest
        if self.uncertainty_code is not None:
            payload["uncertainty_code"] = self.uncertainty_code
        encoded = json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()


def start_checkpoint(
    *,
    saga_id: str,
    node_id: str,
    application: ApplicationKey,
    idempotency_key: str,
    locks: tuple[TypedLock, ...],
    state_identity: StateIdentity | None = None,
) -> ExecutionCheckpoint:
    """Create the immutable PLANNED checkpoint at sequence zero."""
    if state_identity is not None and state_identity.application is not application:
        raise ValueError("state identity application does not match checkpoint application")
    for lock in locks:
        if lock.application is not None and lock.application is not application:
            raise ValueError("typed lock application does not match checkpoint application")
    ordered_locks = canonical_lock_order(locks)
    return ExecutionCheckpoint(
        saga_id_digest=_opaque_digest(saga_id, field_name="saga_id"),
        checkpoint_index=0,
        node_id=_semantic_token(node_id, field_name="node_id"),
        application=application,
        state=ExecutionLifecycleState.PLANNED,
        idempotency_key=idempotency_key,
        lock_keys=tuple(lock.lock_key for lock in ordered_locks),
        state_identity_digest=(
            state_identity.identity_digest if state_identity is not None else None
        ),
    )


def transition_checkpoint(
    checkpoint: ExecutionCheckpoint,
    next_state: ExecutionLifecycleState,
    *,
    result_digest: str | None = None,
    uncertainty_code: str | None = None,
) -> ExecutionCheckpoint:
    """Advance one checkpoint monotonically through the closed lifecycle."""
    if next_state not in _ALLOWED_TRANSITIONS[checkpoint.state]:
        raise ValueError(
            f"invalid lifecycle transition: {checkpoint.state.value}->{next_state.value}"
        )
    return replace(
        checkpoint,
        checkpoint_index=checkpoint.checkpoint_index + 1,
        state=next_state,
        result_digest=result_digest,
        uncertainty_code=uncertainty_code,
    )


def validate_checkpoint_chain(
    checkpoints: tuple[ExecutionCheckpoint, ...],
) -> None:
    """Validate one append-only checkpoint chain for a single saga node."""
    if not checkpoints:
        raise ValueError("checkpoint chain must not be empty")
    first = checkpoints[0]
    if first.checkpoint_index != 0 or first.state is not ExecutionLifecycleState.PLANNED:
        raise ValueError("checkpoint chain must start at PLANNED index zero")

    for expected_index, checkpoint in enumerate(checkpoints):
        if checkpoint.checkpoint_index != expected_index:
            raise ValueError("checkpoint indices must be contiguous and monotonic")
        if (
            checkpoint.saga_id_digest != first.saga_id_digest
            or checkpoint.node_id != first.node_id
            or checkpoint.application is not first.application
            or checkpoint.idempotency_key != first.idempotency_key
            or checkpoint.lock_keys != first.lock_keys
            or checkpoint.state_identity_digest != first.state_identity_digest
        ):
            raise ValueError("checkpoint identity/bindings cannot change within a chain")
        if expected_index == 0:
            continue
        previous = checkpoints[expected_index - 1]
        if checkpoint.state not in _ALLOWED_TRANSITIONS[previous.state]:
            raise ValueError("checkpoint chain contains invalid lifecycle transition")
        if previous.terminal:
            raise ValueError("terminal checkpoint cannot have successors")


__all__ = [
    "ExecutionCheckpoint",
    "ExecutionLifecycleState",
    "start_checkpoint",
    "transition_checkpoint",
    "validate_checkpoint_chain",
]
