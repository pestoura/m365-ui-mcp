"""Bounded execution provenance envelope for CORE-047.

Provenance records semantic execution context without retaining raw operation
identifiers, Microsoft resource ids, tenant content, or browser/session secrets.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum

from m365_mcp.application_registry import ApplicationKey
from m365_mcp.policy import Decision
from m365_mcp.security_tiers import SecurityTier


class ExecutionMode(StrEnum):
    """Closed provenance modes."""

    MOCK = "MOCK"
    LIVE = "LIVE"
    SIMULATION = "SIMULATION"


def _digest(value: str, *, field_name: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{field_name} must not be empty")
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _validate_digest(value: str, *, field_name: str) -> None:
    if len(value) != 64 or any(char not in "0123456789abcdef" for char in value):
        raise ValueError(f"{field_name} must be lowercase SHA-256 hex")


def _aware(value: datetime, *, field_name: str) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} must be timezone-aware")
    return value.astimezone(UTC)


def _semantic_token(value: str, *, field_name: str) -> str:
    normalized = value.strip()
    if not normalized or any(char.isspace() for char in normalized):
        raise ValueError(f"{field_name} must be a non-empty semantic token")
    return normalized


@dataclass(frozen=True)
class ExecutionProvenance:
    """Immutable semantic provenance attached to one produced result."""

    schema_version: str
    operation_id_digest: str
    application: ApplicationKey
    tool_name: str
    tool_version: str
    mode: ExecutionMode
    policy_decision: Decision
    security_tier: SecurityTier
    started_at: datetime
    completed_at: datetime
    state_identity_digest: str | None = None
    checkpoint_digest: str | None = None
    evidence_reference_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.schema_version != "execution-provenance-v1":
            raise ValueError("unsupported execution provenance schema")
        _validate_digest(self.operation_id_digest, field_name="operation_id_digest")
        _semantic_token(self.tool_name, field_name="tool_name")
        if not self.tool_version.strip():
            raise ValueError("tool_version must not be empty")
        started = _aware(self.started_at, field_name="started_at")
        completed = _aware(self.completed_at, field_name="completed_at")
        if completed < started:
            raise ValueError("completed_at must not precede started_at")
        if self.state_identity_digest is not None:
            _validate_digest(
                self.state_identity_digest,
                field_name="state_identity_digest",
            )
        if self.checkpoint_digest is not None:
            _validate_digest(self.checkpoint_digest, field_name="checkpoint_digest")
        for reference_id in self.evidence_reference_ids:
            _validate_digest(reference_id, field_name="evidence_reference_id")
        if len(set(self.evidence_reference_ids)) != len(self.evidence_reference_ids):
            raise ValueError("evidence_reference_ids must be unique")
        if self.mode is ExecutionMode.LIVE and not self.evidence_reference_ids:
            raise ValueError("LIVE provenance requires at least one evidence reference")

    @property
    def duration_ms(self) -> int:
        started = _aware(self.started_at, field_name="started_at")
        completed = _aware(self.completed_at, field_name="completed_at")
        return max(0, int((completed - started).total_seconds() * 1000))

    def to_projection(self) -> dict[str, object]:
        """Return bounded provenance metadata safe for result envelopes."""
        projection: dict[str, object] = {
            "schema_version": self.schema_version,
            "operation_id_digest": self.operation_id_digest,
            "application": self.application.value,
            "tool_name": self.tool_name,
            "tool_version": self.tool_version,
            "mode": self.mode.value,
            "policy_decision": self.policy_decision.value,
            "security_tier": self.security_tier.name,
            "started_at": _aware(self.started_at, field_name="started_at").isoformat(),
            "completed_at": _aware(self.completed_at, field_name="completed_at").isoformat(),
            "duration_ms": self.duration_ms,
            "evidence_reference_ids": self.evidence_reference_ids,
        }
        if self.state_identity_digest is not None:
            projection["state_identity_digest"] = self.state_identity_digest
        if self.checkpoint_digest is not None:
            projection["checkpoint_digest"] = self.checkpoint_digest
        return projection

    @property
    def provenance_digest(self) -> str:
        encoded = json.dumps(
            self.to_projection(),
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()


def make_execution_provenance(
    *,
    operation_id: str,
    application: ApplicationKey,
    tool_name: str,
    tool_version: str,
    mode: ExecutionMode,
    policy_decision: Decision,
    security_tier: SecurityTier,
    started_at: datetime,
    completed_at: datetime,
    state_identity_digest: str | None = None,
    checkpoint_digest: str | None = None,
    evidence_reference_ids: tuple[str, ...] = (),
) -> ExecutionProvenance:
    """Construct provenance while immediately discarding the raw operation id."""
    return ExecutionProvenance(
        schema_version="execution-provenance-v1",
        operation_id_digest=_digest(operation_id, field_name="operation_id"),
        application=application,
        tool_name=tool_name,
        tool_version=tool_version,
        mode=mode,
        policy_decision=policy_decision,
        security_tier=security_tier,
        started_at=started_at,
        completed_at=completed_at,
        state_identity_digest=state_identity_digest,
        checkpoint_digest=checkpoint_digest,
        evidence_reference_ids=evidence_reference_ids,
    )


__all__ = [
    "ExecutionMode",
    "ExecutionProvenance",
    "make_execution_provenance",
]
