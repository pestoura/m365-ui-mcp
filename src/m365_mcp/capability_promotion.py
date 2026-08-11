"""Fail-closed evidence-to-capability promotion decisions.

REL-025 consumes sanitized live-probe evidence only. It never drives a browser,
exports session material, widens the public tool surface, or converts synthetic
evidence into a live-support claim.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Any

from m365_mcp.capability_registry import CapabilityRegistry, ScopedCapability

_DIGEST_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
_IDENTIFIER_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")


class PromotionEvidenceSource(StrEnum):
    """Closed evidence origins accepted by the promotion automaton."""

    LIVE_UI = "LIVE_UI"
    MOCK = "MOCK"
    SYNTHETIC = "SYNTHETIC"


class LiveSupportState(StrEnum):
    """Repository-side support states used by REL-025 decisions."""

    LIVE_UNOBSERVED = "LIVE_UNOBSERVED"
    SUPPORTED_LIVE = "SUPPORTED_LIVE"
    RE_ATTESTATION_REQUIRED = "RE_ATTESTATION_REQUIRED"


class PromotionAction(StrEnum):
    """Fail-closed disposition produced by the automaton."""

    PROMOTE = "PROMOTE"
    HOLD = "HOLD"
    RE_ATTESTATION_REQUIRED = "RE_ATTESTATION_REQUIRED"
    DEMOTE = "DEMOTE"


@dataclass(frozen=True)
class LiveCapabilityEvidence:
    """Sanitized machine-readable evidence for one exact scoped capability."""

    application: str
    surface: str
    account_scope: str
    container_scope: str
    capability: str
    environment_id: str
    observed_at: datetime
    source: PromotionEvidenceSource
    contract_set_digest: str
    passed_gate_ids: tuple[str, ...]
    acceptance_ok: bool
    readback_ok: bool

    def __post_init__(self) -> None:
        for name in (
            "application",
            "surface",
            "account_scope",
            "container_scope",
            "capability",
            "environment_id",
        ):
            value = getattr(self, name)
            if not _IDENTIFIER_RE.fullmatch(value):
                raise ValueError(f"invalid promotion evidence {name}")
        if not _DIGEST_RE.fullmatch(self.contract_set_digest):
            raise ValueError("invalid promotion evidence contract-set digest")
        if self.observed_at.tzinfo is None or self.observed_at.utcoffset() is None:
            raise ValueError("promotion evidence timestamp must be timezone-aware")
        object.__setattr__(self, "observed_at", self.observed_at.astimezone(UTC))
        if len(self.passed_gate_ids) != len(set(self.passed_gate_ids)):
            raise ValueError("promotion evidence contains duplicate gate ids")
        if any(not _IDENTIFIER_RE.fullmatch(item) for item in self.passed_gate_ids):
            raise ValueError("invalid promotion evidence gate id")

    @property
    def identity(self) -> tuple[str, str, str, str, str]:
        return (
            self.application,
            self.surface,
            self.account_scope,
            self.container_scope,
            self.capability,
        )


@dataclass(frozen=True)
class PromotionPolicy:
    """Expected live boundary and prerequisite gates for one evaluation."""

    environment_id: str
    current_contract_set_digest: str
    required_gate_ids: tuple[str, ...]
    max_age: timedelta
    dependencies_accepted: bool

    def __post_init__(self) -> None:
        if not _IDENTIFIER_RE.fullmatch(self.environment_id):
            raise ValueError("invalid promotion policy environment id")
        if not _DIGEST_RE.fullmatch(self.current_contract_set_digest):
            raise ValueError("invalid promotion policy contract-set digest")
        if self.max_age <= timedelta(0):
            raise ValueError("promotion evidence max age must be positive")
        if len(self.required_gate_ids) != len(set(self.required_gate_ids)):
            raise ValueError("promotion policy contains duplicate gate ids")
        if any(not _IDENTIFIER_RE.fullmatch(item) for item in self.required_gate_ids):
            raise ValueError("invalid promotion policy gate id")


@dataclass(frozen=True)
class PromotionDecision:
    """Deterministic target support state plus auditable reason codes."""

    action: PromotionAction
    target_state: LiveSupportState
    reasons: tuple[str, ...]

    @property
    def promotable(self) -> bool:
        return self.action is PromotionAction.PROMOTE

    def to_dict(self) -> dict[str, object]:
        return {
            "action": self.action.value,
            "target_state": self.target_state.value,
            "promotable": self.promotable,
            "reasons": list(self.reasons),
        }


def evidence_from_dict(data: dict[str, Any]) -> LiveCapabilityEvidence:
    """Parse a strict evidence artifact and reject unknown fields."""
    allowed = {
        "application",
        "surface",
        "account_scope",
        "container_scope",
        "capability",
        "environment_id",
        "observed_at",
        "source",
        "contract_set_digest",
        "passed_gate_ids",
        "acceptance_ok",
        "readback_ok",
    }
    if set(data) != allowed:
        raise ValueError("promotion evidence must contain the exact required fields")
    raw_gates = data["passed_gate_ids"]
    if not isinstance(raw_gates, list) or not all(isinstance(item, str) for item in raw_gates):
        raise ValueError("passed_gate_ids must be a list of strings")
    observed_at = data["observed_at"]
    if not isinstance(observed_at, str):
        raise ValueError("observed_at must be an ISO-8601 string")
    timestamp = datetime.fromisoformat(observed_at.replace("Z", "+00:00"))
    if type(data["acceptance_ok"]) is not bool or type(data["readback_ok"]) is not bool:
        raise ValueError("acceptance_ok and readback_ok must be booleans")
    return LiveCapabilityEvidence(
        application=str(data["application"]),
        surface=str(data["surface"]),
        account_scope=str(data["account_scope"]),
        container_scope=str(data["container_scope"]),
        capability=str(data["capability"]),
        environment_id=str(data["environment_id"]),
        observed_at=timestamp,
        source=PromotionEvidenceSource(str(data["source"])),
        contract_set_digest=str(data["contract_set_digest"]),
        passed_gate_ids=tuple(raw_gates),
        acceptance_ok=data["acceptance_ok"],
        readback_ok=data["readback_ok"],
    )


def evaluate_promotion(
    registry: CapabilityRegistry,
    evidence: LiveCapabilityEvidence,
    policy: PromotionPolicy,
    *,
    previous_state: LiveSupportState = LiveSupportState.LIVE_UNOBSERVED,
    now: datetime | None = None,
) -> PromotionDecision:
    """Evaluate exact live evidence; every ambiguity fails closed."""
    current_time = (now or datetime.now(UTC)).astimezone(UTC)
    if current_time.tzinfo is None or current_time.utcoffset() is None:
        raise ValueError("promotion evaluation time must be timezone-aware")

    declared = {item.identity for item in registry.declared_definitions()}
    if evidence.identity not in declared:
        return _invalid(previous_state, "CAPABILITY_SCOPE_NOT_DECLARED")
    if evidence.source is not PromotionEvidenceSource.LIVE_UI:
        return _invalid(previous_state, "NON_LIVE_EVIDENCE_CANNOT_PROMOTE")
    if evidence.environment_id != policy.environment_id:
        return _invalid(previous_state, "ENVIRONMENT_SCOPE_MISMATCH")
    if evidence.contract_set_digest != policy.current_contract_set_digest:
        return _reattest(previous_state, "UI_CONTRACT_DIGEST_MISMATCH")
    if evidence.observed_at > current_time:
        return _reattest(previous_state, "EVIDENCE_TIMESTAMP_IN_FUTURE")
    if current_time - evidence.observed_at > policy.max_age:
        return _reattest(previous_state, "LIVE_EVIDENCE_STALE")

    missing_gates = tuple(
        gate for gate in policy.required_gate_ids if gate not in set(evidence.passed_gate_ids)
    )
    if missing_gates:
        return _invalid(
            previous_state,
            *(f"REQUIRED_GATE_MISSING:{gate}" for gate in missing_gates),
        )
    if not evidence.acceptance_ok:
        return _invalid(previous_state, "LIVE_ACCEPTANCE_NOT_CONFIRMED")
    if not evidence.readback_ok:
        return _invalid(previous_state, "READBACK_NOT_CONFIRMED")
    if not policy.dependencies_accepted:
        return PromotionDecision(
            PromotionAction.HOLD,
            LiveSupportState.LIVE_UNOBSERVED,
            ("LIVE_ACCEPTANCE_DEPENDENCIES_UNMET",),
        )

    return PromotionDecision(
        PromotionAction.PROMOTE,
        LiveSupportState.SUPPORTED_LIVE,
        ("ALL_PROMOTION_EVIDENCE_VALID",),
    )


def _invalid(previous_state: LiveSupportState, *reasons: str) -> PromotionDecision:
    if previous_state is LiveSupportState.SUPPORTED_LIVE:
        return PromotionDecision(
            PromotionAction.DEMOTE,
            LiveSupportState.RE_ATTESTATION_REQUIRED,
            tuple(reasons),
        )
    return PromotionDecision(
        PromotionAction.HOLD,
        LiveSupportState.LIVE_UNOBSERVED,
        tuple(reasons),
    )


def _reattest(previous_state: LiveSupportState, *reasons: str) -> PromotionDecision:
    action = (
        PromotionAction.DEMOTE
        if previous_state is LiveSupportState.SUPPORTED_LIVE
        else PromotionAction.RE_ATTESTATION_REQUIRED
    )
    return PromotionDecision(
        action,
        LiveSupportState.RE_ATTESTATION_REQUIRED,
        tuple(reasons),
    )


def scoped_capability_from_evidence(evidence: LiveCapabilityEvidence) -> ScopedCapability:
    """Project the exact semantic scope without enabling it in a registry."""
    return ScopedCapability(
        application=evidence.application,
        surface=evidence.surface,
        account_scope=evidence.account_scope,
        container_scope=evidence.container_scope,
        capability=evidence.capability,
    )


__all__ = [
    "LiveCapabilityEvidence",
    "LiveSupportState",
    "PromotionAction",
    "PromotionDecision",
    "PromotionEvidenceSource",
    "PromotionPolicy",
    "evaluate_promotion",
    "evidence_from_dict",
    "scoped_capability_from_evidence",
]
