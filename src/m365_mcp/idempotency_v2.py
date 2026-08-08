"""Application-neutral idempotency and replay rules for CORE-038.

The v2 model binds one operation to CORE-037 state identity plus request/result
digests. Retry decisions are explicit about read-back evidence so an uncertain
mutation is never blindly repeated.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, replace
from enum import StrEnum
from typing import Any

from m365_mcp.state_identity import StateIdentity


class OperationPhase(StrEnum):
    """Closed lifecycle states relevant to replay protection."""

    RESERVED = "RESERVED"
    COMPLETED = "COMPLETED"
    FAILED_PRE_EFFECT = "FAILED_PRE_EFFECT"
    EFFECT_UNVERIFIED = "EFFECT_UNVERIFIED"


class ReadBackOutcome(StrEnum):
    """Bounded read-back evidence used by retry decisions."""

    NOT_RUN = "NOT_RUN"
    EFFECT_PRESENT = "EFFECT_PRESENT"
    EFFECT_ABSENT = "EFFECT_ABSENT"
    AMBIGUOUS = "AMBIGUOUS"


class RetryAction(StrEnum):
    """Closed retry/replay decisions."""

    EXECUTE = "EXECUTE"
    REPLAY_RESULT = "REPLAY_RESULT"
    RETRY_SAFE = "RETRY_SAFE"
    READ_BACK_REQUIRED = "READ_BACK_REQUIRED"
    DO_NOT_RETRY = "DO_NOT_RETRY"
    DENY_BINDING_MISMATCH = "DENY_BINDING_MISMATCH"


def _sha256_payload(value: object) -> str:
    encoded = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def request_digest(payload: dict[str, Any]) -> str:
    """Hash a semantic request without retaining its potentially sensitive values."""
    return _sha256_payload(payload)


def result_digest(result: object) -> str:
    """Hash a semantic result for operation/result association."""
    return _sha256_payload(result)


def make_idempotency_key(
    operation: str,
    identity: StateIdentity,
    request_hash: str,
) -> str:
    """Derive a stable key from operation, scoped identity and request digest."""
    normalized_operation = operation.strip()
    if not normalized_operation or any(char.isspace() for char in normalized_operation):
        raise ValueError("operation must be a non-empty semantic token")
    _validate_digest(request_hash, field_name="request_hash")
    return _sha256_payload(
        {
            "operation": normalized_operation,
            "identity_digest": identity.identity_digest,
            "request_digest": request_hash,
        }
    )


def _validate_digest(value: str, *, field_name: str) -> None:
    if len(value) != 64 or any(char not in "0123456789abcdef" for char in value):
        raise ValueError(f"{field_name} must be lowercase SHA-256 hex")


@dataclass(frozen=True)
class IdempotencyRecordV2:
    """One operation binding with replay-safe lifecycle metadata."""

    key: str
    operation: str
    identity_digest: str
    request_digest: str
    phase: OperationPhase
    read_back_required: bool
    result_digest: str | None = None

    def __post_init__(self) -> None:
        _validate_digest(self.key, field_name="key")
        _validate_digest(self.identity_digest, field_name="identity_digest")
        _validate_digest(self.request_digest, field_name="request_digest")
        if not self.operation.strip() or any(char.isspace() for char in self.operation):
            raise ValueError("operation must be a non-empty semantic token")
        if self.result_digest is not None:
            _validate_digest(self.result_digest, field_name="result_digest")
        if self.phase is OperationPhase.COMPLETED and self.result_digest is None:
            raise ValueError("completed record requires result_digest")
        if self.phase is not OperationPhase.COMPLETED and self.result_digest is not None:
            raise ValueError("only completed record may carry result_digest")

    def binding_matches(
        self,
        *,
        operation: str,
        identity: StateIdentity,
        request_hash: str,
    ) -> bool:
        """Verify that a retry addresses the exact same semantic operation."""
        return (
            self.operation == operation
            and self.identity_digest == identity.identity_digest
            and self.request_digest == request_hash
            and self.key == make_idempotency_key(operation, identity, request_hash)
        )


def reserve_operation(
    operation: str,
    identity: StateIdentity,
    payload: dict[str, Any],
    *,
    read_back_required: bool,
) -> IdempotencyRecordV2:
    """Create a v2 reservation without retaining request data."""
    digest = request_digest(payload)
    return IdempotencyRecordV2(
        key=make_idempotency_key(operation, identity, digest),
        operation=operation,
        identity_digest=identity.identity_digest,
        request_digest=digest,
        phase=OperationPhase.RESERVED,
        read_back_required=read_back_required,
    )


def associate_result(record: IdempotencyRecordV2, result: object) -> IdempotencyRecordV2:
    """Complete an operation by binding its semantic result digest."""
    if record.phase is not OperationPhase.RESERVED:
        raise ValueError("only reserved operation can associate a result")
    return replace(
        record,
        phase=OperationPhase.COMPLETED,
        result_digest=result_digest(result),
    )


def mark_failed_pre_effect(record: IdempotencyRecordV2) -> IdempotencyRecordV2:
    """Mark a failure proven to have occurred before Microsoft state could change."""
    if record.phase is not OperationPhase.RESERVED:
        raise ValueError("only reserved operation can fail before effect")
    return replace(record, phase=OperationPhase.FAILED_PRE_EFFECT)


def mark_effect_unverified(record: IdempotencyRecordV2) -> IdempotencyRecordV2:
    """Mark an operation whose external effect must be reconciled before retry."""
    if record.phase is not OperationPhase.RESERVED:
        raise ValueError("only reserved operation can become effect-unverified")
    return replace(record, phase=OperationPhase.EFFECT_UNVERIFIED)


def resolve_retry(
    record: IdempotencyRecordV2 | None,
    *,
    operation: str,
    identity: StateIdentity,
    payload: dict[str, Any],
    read_back: ReadBackOutcome = ReadBackOutcome.NOT_RUN,
) -> RetryAction:
    """Return the only safe action for a repeated semantic operation."""
    digest = request_digest(payload)
    if record is None:
        return RetryAction.EXECUTE

    if not record.binding_matches(
        operation=operation,
        identity=identity,
        request_hash=digest,
    ):
        return RetryAction.DENY_BINDING_MISMATCH

    if record.phase is OperationPhase.COMPLETED:
        return RetryAction.REPLAY_RESULT

    if record.phase is OperationPhase.FAILED_PRE_EFFECT:
        return RetryAction.RETRY_SAFE

    if not record.read_back_required:
        if record.phase is OperationPhase.RESERVED:
            return RetryAction.RETRY_SAFE
        return RetryAction.DO_NOT_RETRY

    if read_back is ReadBackOutcome.EFFECT_PRESENT:
        return RetryAction.DO_NOT_RETRY
    if read_back is ReadBackOutcome.EFFECT_ABSENT:
        return RetryAction.RETRY_SAFE
    return RetryAction.READ_BACK_REQUIRED


__all__ = [
    "IdempotencyRecordV2",
    "OperationPhase",
    "ReadBackOutcome",
    "RetryAction",
    "associate_result",
    "make_idempotency_key",
    "mark_effect_unverified",
    "mark_failed_pre_effect",
    "request_digest",
    "reserve_operation",
    "resolve_retry",
    "result_digest",
]
