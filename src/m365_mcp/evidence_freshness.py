"""Versioned lifetime and revalidation policy for UI capability evidence."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from pathlib import Path
from typing import Any

from m365_mcp.capability_evidence import CapabilityEvidenceRecord
from m365_mcp.contracts import contracts_dir
from m365_mcp.ui_contract_store import UIContractFragment, UIContractSet
from m365_mcp.ui_drift import UILifecycleState

_MIN_MAX_AGE_SECONDS = 60
_MAX_MAX_AGE_SECONDS = 2_592_000
_ALLOWED_POLICY_STATES = {
    UILifecycleState.STALE,
    UILifecycleState.RE_ATTESTATION_REQUIRED,
}


class EvidenceFreshnessReason(StrEnum):
    """Closed reason codes for effective evidence freshness."""

    EVIDENCE_FRESH = "EVIDENCE_FRESH"
    EVIDENCE_EXPIRED = "EVIDENCE_EXPIRED"
    EVIDENCE_MISSING = "EVIDENCE_MISSING"
    EVIDENCE_TIMESTAMP_IN_FUTURE = "EVIDENCE_TIMESTAMP_IN_FUTURE"
    SOURCE_STALE = "SOURCE_STALE"
    SOURCE_DRIFTED = "SOURCE_DRIFTED"
    SOURCE_RE_ATTESTATION_REQUIRED = "SOURCE_RE_ATTESTATION_REQUIRED"


@dataclass(frozen=True)
class EvidenceLifetimePolicy:
    """Validated, reviewable policy for the maximum age of healthy UI evidence."""

    schema_version: str
    policy_id: str
    max_age_seconds: int
    expiry_state: UILifecycleState | str
    missing_evidence_state: UILifecycleState | str
    future_timestamp_state: UILifecycleState | str

    def __post_init__(self) -> None:
        if not self.schema_version or any(char.isspace() for char in self.schema_version):
            raise ValueError("evidence lifetime policy schema version is invalid")
        if not self.policy_id or self.policy_id != self.policy_id.strip():
            raise ValueError("evidence lifetime policy id is invalid")
        if not _MIN_MAX_AGE_SECONDS <= self.max_age_seconds <= _MAX_MAX_AGE_SECONDS:
            raise ValueError("evidence lifetime max age is outside bounded range")
        for field_name in (
            "expiry_state",
            "missing_evidence_state",
            "future_timestamp_state",
        ):
            try:
                state = UILifecycleState(getattr(self, field_name))
            except ValueError as exc:
                raise ValueError(f"invalid evidence lifetime {field_name}") from exc
            if state not in _ALLOWED_POLICY_STATES:
                raise ValueError(f"unsafe evidence lifetime {field_name}")
            object.__setattr__(self, field_name, state)

    @property
    def max_age(self) -> timedelta:
        return timedelta(seconds=self.max_age_seconds)

    def canonical_payload(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "policy_id": self.policy_id,
            "max_age_seconds": self.max_age_seconds,
            "expiry_state": UILifecycleState(self.expiry_state).value,
            "missing_evidence_state": UILifecycleState(self.missing_evidence_state).value,
            "future_timestamp_state": UILifecycleState(self.future_timestamp_state).value,
        }

    def digest(self) -> str:
        encoded = json.dumps(
            self.canonical_payload(),
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
        return f"sha256:{hashlib.sha256(encoded).hexdigest()}"


@dataclass(frozen=True)
class EvidenceFreshnessAssessment:
    """Effective lifecycle state derived from persisted evidence plus lifetime policy."""

    fragment_id: str
    effective_state: UILifecycleState
    reason: EvidenceFreshnessReason
    policy_digest: str
    evidence_id: str | None
    recorded_at: datetime | None
    expires_at: datetime | None

    @property
    def revalidation_required(self) -> bool:
        return self.effective_state is not UILifecycleState.HEALTHY

    def to_dict(self) -> dict[str, object]:
        return {
            "fragment_id": self.fragment_id,
            "effective_state": self.effective_state.value,
            "reason": self.reason.value,
            "policy_digest": self.policy_digest,
            "evidence_id": self.evidence_id,
            "recorded_at": _format_optional_timestamp(self.recorded_at),
            "expires_at": _format_optional_timestamp(self.expires_at),
            "revalidation_required": self.revalidation_required,
        }


def load_evidence_lifetime_policy(path: Path | None = None) -> EvidenceLifetimePolicy:
    """Load the versioned policy from the repository contract surface."""
    policy_path = path or (contracts_dir() / "ui_evidence_lifetime_policy.json")
    data = json.loads(policy_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("evidence lifetime policy must be a JSON object")
    allowed = {
        "schema_version",
        "policy_id",
        "max_age_seconds",
        "expiry_state",
        "missing_evidence_state",
        "future_timestamp_state",
    }
    if set(data) != allowed:
        raise ValueError("evidence lifetime policy fields do not match the closed schema")
    max_age = data.get("max_age_seconds")
    if not isinstance(max_age, int) or isinstance(max_age, bool):
        raise ValueError("evidence lifetime max age must be an integer")
    return EvidenceLifetimePolicy(
        schema_version=str(data["schema_version"]),
        policy_id=str(data["policy_id"]),
        max_age_seconds=max_age,
        expiry_state=str(data["expiry_state"]),
        missing_evidence_state=str(data["missing_evidence_state"]),
        future_timestamp_state=str(data["future_timestamp_state"]),
    )


def assess_contract_evidence_freshness(
    contract_set: UIContractSet,
    records: tuple[CapabilityEvidenceRecord, ...],
    *,
    policy: EvidenceLifetimePolicy,
    now: datetime,
) -> tuple[EvidenceFreshnessAssessment, ...]:
    """Assess every contract fragment without ever promoting a degraded source record."""
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("evidence freshness evaluation time must be timezone-aware")
    now_utc = now.astimezone(UTC)
    by_fragment: dict[str, CapabilityEvidenceRecord] = {}
    contract_digest = contract_set.digest()
    fragments = {fragment.fragment_id: fragment for fragment in contract_set.fragments}

    for record in records:
        if record.fragment_id in by_fragment:
            raise ValueError("evidence freshness input contains duplicate fragment records")
        fragment = fragments.get(record.fragment_id)
        if fragment is None:
            raise ValueError("evidence freshness input references unknown fragment")
        _validate_record_binding(record, fragment, contract_digest)
        by_fragment[record.fragment_id] = record

    return tuple(
        _assess_fragment(
            fragment,
            by_fragment.get(fragment.fragment_id),
            policy=policy,
            now=now_utc,
        )
        for fragment in contract_set.fragments
    )


def lifecycle_overlay_from_freshness(
    assessments: tuple[EvidenceFreshnessAssessment, ...],
) -> dict[str, UILifecycleState]:
    """Return the capability-scoped overlay consumed by UIContract projection."""
    fragment_ids = tuple(item.fragment_id for item in assessments)
    if len(fragment_ids) != len(set(fragment_ids)):
        raise ValueError("freshness assessments contain duplicate fragments")
    return {item.fragment_id: item.effective_state for item in assessments}


def _assess_fragment(
    fragment: UIContractFragment,
    record: CapabilityEvidenceRecord | None,
    *,
    policy: EvidenceLifetimePolicy,
    now: datetime,
) -> EvidenceFreshnessAssessment:
    policy_digest = policy.digest()
    if record is None:
        return EvidenceFreshnessAssessment(
            fragment_id=fragment.fragment_id,
            effective_state=UILifecycleState(policy.missing_evidence_state),
            reason=EvidenceFreshnessReason.EVIDENCE_MISSING,
            policy_digest=policy_digest,
            evidence_id=None,
            recorded_at=None,
            expires_at=None,
        )

    source_state = UILifecycleState(record.lifecycle_state)
    expires_at = record.recorded_at + policy.max_age
    if source_state is UILifecycleState.DRIFTED:
        return _assessment(
            record,
            state=UILifecycleState.DRIFTED,
            reason=EvidenceFreshnessReason.SOURCE_DRIFTED,
            policy_digest=policy_digest,
            expires_at=expires_at,
        )
    if source_state is UILifecycleState.RE_ATTESTATION_REQUIRED:
        return _assessment(
            record,
            state=UILifecycleState.RE_ATTESTATION_REQUIRED,
            reason=EvidenceFreshnessReason.SOURCE_RE_ATTESTATION_REQUIRED,
            policy_digest=policy_digest,
            expires_at=expires_at,
        )
    if source_state is UILifecycleState.STALE:
        return _assessment(
            record,
            state=UILifecycleState.STALE,
            reason=EvidenceFreshnessReason.SOURCE_STALE,
            policy_digest=policy_digest,
            expires_at=expires_at,
        )
    if record.recorded_at > now:
        return _assessment(
            record,
            state=UILifecycleState(policy.future_timestamp_state),
            reason=EvidenceFreshnessReason.EVIDENCE_TIMESTAMP_IN_FUTURE,
            policy_digest=policy_digest,
            expires_at=expires_at,
        )
    if now >= expires_at:
        return _assessment(
            record,
            state=UILifecycleState(policy.expiry_state),
            reason=EvidenceFreshnessReason.EVIDENCE_EXPIRED,
            policy_digest=policy_digest,
            expires_at=expires_at,
        )
    return _assessment(
        record,
        state=UILifecycleState.HEALTHY,
        reason=EvidenceFreshnessReason.EVIDENCE_FRESH,
        policy_digest=policy_digest,
        expires_at=expires_at,
    )


def _assessment(
    record: CapabilityEvidenceRecord,
    *,
    state: UILifecycleState,
    reason: EvidenceFreshnessReason,
    policy_digest: str,
    expires_at: datetime,
) -> EvidenceFreshnessAssessment:
    return EvidenceFreshnessAssessment(
        fragment_id=record.fragment_id,
        effective_state=state,
        reason=reason,
        policy_digest=policy_digest,
        evidence_id=record.evidence_id,
        recorded_at=record.recorded_at,
        expires_at=expires_at,
    )


def _validate_record_binding(
    record: CapabilityEvidenceRecord,
    fragment: UIContractFragment,
    contract_digest: str,
) -> None:
    if record.contract_set_digest != contract_digest:
        raise ValueError("evidence freshness record contract-set digest mismatch")
    expected = (
        fragment.fragment_version,
        fragment.scope,
        fragment.application,
        fragment.surface,
    )
    actual = (
        record.fragment_version,
        record.scope,
        record.application,
        record.surface,
    )
    if actual != expected:
        raise ValueError("evidence freshness record fragment metadata mismatch")


def _format_optional_timestamp(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.astimezone(UTC).isoformat(timespec="microseconds").replace("+00:00", "Z")


__all__ = [
    "EvidenceFreshnessAssessment",
    "EvidenceFreshnessReason",
    "EvidenceLifetimePolicy",
    "assess_contract_evidence_freshness",
    "lifecycle_overlay_from_freshness",
    "load_evidence_lifetime_policy",
]
