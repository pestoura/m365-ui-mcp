"""Deterministic UI attestation campaign planning and sanitized evaluation.

This module never drives a browser. It plans bounded campaigns and evaluates
sanitized observations produced by an explicitly controlled live-UI run.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from m365_mcp.capability_evidence import CapabilityEvidenceRecord
from m365_mcp.locators import locator_plan_from_metadata
from m365_mcp.ui_contract_store import UIContractFragment, UIContractSet
from m365_mcp.ui_drift import UILifecycleState

_DIGEST_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
_LOCALE_RE = re.compile(r"^[A-Za-z]{2,3}(?:-[A-Za-z0-9]{2,8})*$")


class AttestationLevel(StrEnum):
    """Evidence level requested by an attestation campaign."""

    DISCOVERY = "DISCOVERY"
    UI = "UI"
    READ = "READ"
    MUTATION = "MUTATION"


class ObservationSource(StrEnum):
    """Closed evidence origins; mock evidence can never promote live support."""

    LIVE_UI = "LIVE_UI"
    MOCK = "MOCK"


class SelectorObservationResult(StrEnum):
    """Sanitized result of one selector/invariant observation."""

    UNIQUE_MATCH = "UNIQUE_MATCH"
    NO_MATCH = "NO_MATCH"
    AMBIGUOUS = "AMBIGUOUS"
    STRUCTURE_MISMATCH = "STRUCTURE_MISMATCH"


class AttestationDecisionState(StrEnum):
    """Operational disposition of one evaluated observation."""

    PASSED = "PASSED"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    FAILED = "FAILED"


@dataclass(frozen=True)
class AttestationCampaignStep:
    """One selector/invariant that must be observed without exposing locator values."""

    fragment_id: str
    selector_key: str
    contract_status: str
    locator_strategies: tuple[str, ...]
    discovery_required: bool

    def to_dict(self) -> dict[str, object]:
        return {
            "fragment_id": self.fragment_id,
            "selector_key": self.selector_key,
            "contract_status": self.contract_status,
            "locator_strategies": list(self.locator_strategies),
            "discovery_required": self.discovery_required,
        }


@dataclass(frozen=True)
class AttestationCampaign:
    """Deterministic campaign pinned to one exact UIContractSet digest."""

    contract_set_digest: str
    target_level: AttestationLevel
    fragment_ids: tuple[str, ...]
    steps: tuple[AttestationCampaignStep, ...]

    @property
    def campaign_id(self) -> str:
        encoded = _canonical_json(self.canonical_payload())
        return f"sha256:{hashlib.sha256(encoded).hexdigest()}"

    def canonical_payload(self) -> dict[str, object]:
        return {
            "contract_set_digest": self.contract_set_digest,
            "target_level": self.target_level.value,
            "fragment_ids": list(self.fragment_ids),
            "steps": [step.to_dict() for step in self.steps],
        }

    def to_dict(self) -> dict[str, object]:
        return {"campaign_id": self.campaign_id, **self.canonical_payload()}


@dataclass(frozen=True)
class SelectorObservation:
    """Content-free observation for one selector/invariant."""

    selector_key: str
    result: SelectorObservationResult
    structural_digest: str | None = None

    def __post_init__(self) -> None:
        if not self.selector_key or self.selector_key != self.selector_key.strip():
            raise ValueError("selector observation key must be non-empty and trimmed")
        if self.structural_digest is not None and not _DIGEST_RE.fullmatch(
            self.structural_digest
        ):
            raise ValueError("selector structural digest must be sha256")
        if (
            self.result is SelectorObservationResult.UNIQUE_MATCH
            and self.structural_digest is None
        ):
            raise ValueError("unique selector observation requires structural digest")

    def to_dict(self) -> dict[str, object]:
        return {
            "selector_key": self.selector_key,
            "result": self.result.value,
            "structural_digest": self.structural_digest,
        }


@dataclass(frozen=True)
class AttestationObservation:
    """Sanitized observation bundle; contains no page text, DOM, URL or identity."""

    campaign_id: str
    contract_set_digest: str
    fragment_id: str
    fragment_version: str
    target_level: AttestationLevel
    source: ObservationSource
    observed_at: datetime
    selector_observations: tuple[SelectorObservation, ...]
    locale: str | None = None
    ui_surface_signal_digest: str | None = None
    read_probe_ok: bool | None = None
    mutation_applied: bool | None = None
    read_back_ok: bool | None = None
    compensation_proven: bool | None = None
    approval_digest: str | None = None

    def __post_init__(self) -> None:
        for digest_name, digest in (
            ("campaign", self.campaign_id),
            ("contract-set", self.contract_set_digest),
        ):
            if not _DIGEST_RE.fullmatch(digest):
                raise ValueError(f"{digest_name} digest must be sha256")
        if not self.fragment_id or self.fragment_id != self.fragment_id.strip():
            raise ValueError("attestation fragment id must be non-empty and trimmed")
        if not self.fragment_version or any(
            char.isspace() for char in self.fragment_version
        ):
            raise ValueError("attestation fragment version is invalid")
        if self.observed_at.tzinfo is None or self.observed_at.utcoffset() is None:
            raise ValueError("attestation timestamp must be timezone-aware")
        object.__setattr__(self, "observed_at", self.observed_at.astimezone(UTC))
        if not self.selector_observations:
            raise ValueError("attestation observation requires selector observations")
        selector_keys = tuple(item.selector_key for item in self.selector_observations)
        if len(selector_keys) != len(set(selector_keys)):
            raise ValueError("attestation observation contains duplicate selectors")
        if self.locale is not None and not _LOCALE_RE.fullmatch(self.locale):
            raise ValueError("attestation locale is invalid")
        for digest_name, digest in (
            ("UI surface signal", self.ui_surface_signal_digest),
            ("approval", self.approval_digest),
        ):
            if digest is not None and not _DIGEST_RE.fullmatch(digest):
                raise ValueError(f"{digest_name} digest must be sha256")

    def canonical_payload(self) -> dict[str, object]:
        return {
            "campaign_id": self.campaign_id,
            "contract_set_digest": self.contract_set_digest,
            "fragment_id": self.fragment_id,
            "fragment_version": self.fragment_version,
            "target_level": self.target_level.value,
            "source": self.source.value,
            "observed_at": _format_timestamp(self.observed_at),
            "selector_observations": [
                item.to_dict() for item in self.selector_observations
            ],
            "locale": self.locale,
            "ui_surface_signal_digest": self.ui_surface_signal_digest,
            "read_probe_ok": self.read_probe_ok,
            "mutation_applied": self.mutation_applied,
            "read_back_ok": self.read_back_ok,
            "compensation_proven": self.compensation_proven,
            "approval_digest": self.approval_digest,
        }

    def digest(self) -> str:
        encoded = _canonical_json(self.canonical_payload())
        return f"sha256:{hashlib.sha256(encoded).hexdigest()}"


@dataclass(frozen=True)
class AttestationDecision:
    """Bounded evaluation result and the CORE-018 evidence record it produces."""

    state: AttestationDecisionState
    reasons: tuple[str, ...]
    evidence_record: CapabilityEvidenceRecord

    def to_dict(self) -> dict[str, object]:
        return {
            "state": self.state.value,
            "reasons": list(self.reasons),
            "evidence_record": self.evidence_record.to_dict(),
        }


def build_attestation_campaign(
    contract_set: UIContractSet,
    target_level: AttestationLevel | str,
    *,
    fragment_ids: tuple[str, ...] | None = None,
) -> AttestationCampaign:
    """Build a reproducible campaign without exposing raw locator values."""
    level = AttestationLevel(target_level)
    known = {fragment.fragment_id for fragment in contract_set.fragments}
    requested = set(fragment_ids or ())
    unknown = requested - known
    if unknown:
        raise ValueError("attestation campaign references unknown fragment")

    selected = tuple(
        fragment
        for fragment in contract_set.fragments
        if fragment_ids is None or fragment.fragment_id in requested
    )
    if not selected:
        raise ValueError("attestation campaign must target at least one fragment")

    steps: list[AttestationCampaignStep] = []
    for fragment in selected:
        for selector_key, metadata in fragment.selectors.items():
            locator_plan = locator_plan_from_metadata(selector_key, metadata)
            strategies = (
                tuple(candidate.strategy.value for candidate in locator_plan.ordered_candidates())
                if locator_plan is not None
                else ()
            )
            steps.append(
                AttestationCampaignStep(
                    fragment_id=fragment.fragment_id,
                    selector_key=selector_key,
                    contract_status=str(metadata.get("status", "UNVERIFIED_LIVE")),
                    locator_strategies=strategies,
                    discovery_required=locator_plan is None,
                )
            )

    return AttestationCampaign(
        contract_set_digest=contract_set.digest(),
        target_level=level,
        fragment_ids=tuple(fragment.fragment_id for fragment in selected),
        steps=tuple(steps),
    )


def observation_from_dict(data: dict[str, Any]) -> AttestationObservation:
    """Parse a strict sanitized observation document."""
    allowed = {
        "campaign_id",
        "contract_set_digest",
        "fragment_id",
        "fragment_version",
        "target_level",
        "source",
        "observed_at",
        "selector_observations",
        "locale",
        "ui_surface_signal_digest",
        "read_probe_ok",
        "mutation_applied",
        "read_back_ok",
        "compensation_proven",
        "approval_digest",
    }
    if set(data) - allowed:
        raise ValueError("attestation observation contains unknown fields")
    raw_selectors = data.get("selector_observations")
    if not isinstance(raw_selectors, list):
        raise ValueError("selector_observations must be a list")
    selectors: list[SelectorObservation] = []
    for raw in raw_selectors:
        if not isinstance(raw, dict):
            raise ValueError("selector observation must be an object")
        if set(raw) - {"selector_key", "result", "structural_digest"}:
            raise ValueError("selector observation contains unknown fields")
        selectors.append(
            SelectorObservation(
                selector_key=str(raw.get("selector_key", "")),
                result=SelectorObservationResult(str(raw.get("result", ""))),
                structural_digest=(
                    str(raw["structural_digest"])
                    if raw.get("structural_digest") is not None
                    else None
                ),
            )
        )

    observed_at = data.get("observed_at")
    if not isinstance(observed_at, str):
        raise ValueError("observed_at must be an ISO-8601 string")
    try:
        timestamp = datetime.fromisoformat(observed_at.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("observed_at must be valid ISO-8601") from exc

    return AttestationObservation(
        campaign_id=str(data.get("campaign_id", "")),
        contract_set_digest=str(data.get("contract_set_digest", "")),
        fragment_id=str(data.get("fragment_id", "")),
        fragment_version=str(data.get("fragment_version", "")),
        target_level=AttestationLevel(str(data.get("target_level", ""))),
        source=ObservationSource(str(data.get("source", ""))),
        observed_at=timestamp,
        selector_observations=tuple(selectors),
        locale=str(data["locale"]) if data.get("locale") is not None else None,
        ui_surface_signal_digest=(
            str(data["ui_surface_signal_digest"])
            if data.get("ui_surface_signal_digest") is not None
            else None
        ),
        read_probe_ok=_optional_bool(data, "read_probe_ok"),
        mutation_applied=_optional_bool(data, "mutation_applied"),
        read_back_ok=_optional_bool(data, "read_back_ok"),
        compensation_proven=_optional_bool(data, "compensation_proven"),
        approval_digest=(
            str(data["approval_digest"])
            if data.get("approval_digest") is not None
            else None
        ),
    )


def evaluate_attestation_observation(
    contract_set: UIContractSet,
    observation: AttestationObservation,
) -> AttestationDecision:
    """Evaluate one observation without inferring selectors or tenant state."""
    campaign = build_attestation_campaign(
        contract_set,
        observation.target_level,
        fragment_ids=(observation.fragment_id,),
    )
    fragment = _fragment(contract_set, observation.fragment_id)
    structural_errors = _validate_observation_binding(campaign, fragment, observation)
    if structural_errors:
        return _decision(
            fragment,
            observation,
            AttestationDecisionState.FAILED,
            structural_errors,
            UILifecycleState.RE_ATTESTATION_REQUIRED,
        )

    if observation.source is not ObservationSource.LIVE_UI:
        return _decision(
            fragment,
            observation,
            AttestationDecisionState.REVIEW_REQUIRED,
            ("NON_LIVE_EVIDENCE_CANNOT_PROMOTE",),
            UILifecycleState.RE_ATTESTATION_REQUIRED,
        )

    failures = tuple(
        item
        for item in observation.selector_observations
        if item.result is not SelectorObservationResult.UNIQUE_MATCH
    )
    if failures:
        state = (
            UILifecycleState.DRIFTED
            if fragment.effectively_attested
            else UILifecycleState.RE_ATTESTATION_REQUIRED
        )
        return _decision(
            fragment,
            observation,
            AttestationDecisionState.FAILED,
            tuple(f"SELECTOR_{item.result.value}:{item.selector_key}" for item in failures),
            state,
        )

    campaign_steps = tuple(
        step for step in campaign.steps if step.fragment_id == fragment.fragment_id
    )
    discovery_required = tuple(
        step.selector_key for step in campaign_steps if step.discovery_required
    )
    if observation.target_level is not AttestationLevel.DISCOVERY and discovery_required:
        return _decision(
            fragment,
            observation,
            AttestationDecisionState.REVIEW_REQUIRED,
            tuple(f"LOCATOR_DISCOVERY_REQUIRED:{key}" for key in discovery_required),
            UILifecycleState.RE_ATTESTATION_REQUIRED,
        )

    if observation.target_level is AttestationLevel.DISCOVERY:
        return _decision(
            fragment,
            observation,
            AttestationDecisionState.REVIEW_REQUIRED,
            ("DISCOVERY_EVIDENCE_RECORDED_CONTRACT_REVIEW_REQUIRED",),
            UILifecycleState.RE_ATTESTATION_REQUIRED,
        )

    if observation.target_level in {AttestationLevel.READ, AttestationLevel.MUTATION}:
        if not fragment.effectively_attested:
            return _decision(
                fragment,
                observation,
                AttestationDecisionState.REVIEW_REQUIRED,
                ("UI_CONTRACT_MUST_BE_ATTESTED_BEFORE_SEMANTIC_PROBE",),
                UILifecycleState.RE_ATTESTATION_REQUIRED,
            )
        if observation.read_probe_ok is not True:
            return _decision(
                fragment,
                observation,
                AttestationDecisionState.FAILED,
                ("READ_PROBE_NOT_CONFIRMED",),
                UILifecycleState.DRIFTED,
            )

    if observation.target_level is AttestationLevel.MUTATION:
        mutation_failures: list[str] = []
        if observation.approval_digest is None:
            mutation_failures.append("MUTATION_APPROVAL_EVIDENCE_REQUIRED")
        if observation.mutation_applied is not True:
            mutation_failures.append("MUTATION_NOT_CONFIRMED")
        if observation.read_back_ok is not True:
            mutation_failures.append("MUTATION_READ_BACK_NOT_CONFIRMED")
        if observation.compensation_proven is not True:
            mutation_failures.append("MUTATION_COMPENSATION_NOT_PROVEN")
        if mutation_failures:
            return _decision(
                fragment,
                observation,
                AttestationDecisionState.FAILED,
                tuple(mutation_failures),
                UILifecycleState.RE_ATTESTATION_REQUIRED,
            )

    if not fragment.effectively_attested:
        return _decision(
            fragment,
            observation,
            AttestationDecisionState.REVIEW_REQUIRED,
            ("UI_OBSERVATION_PASSED_CONTRACT_ATTESTATION_REVIEW_REQUIRED",),
            UILifecycleState.RE_ATTESTATION_REQUIRED,
        )

    return _decision(
        fragment,
        observation,
        AttestationDecisionState.PASSED,
        (f"{observation.target_level.value}_ATTESTATION_PASSED",),
        UILifecycleState.HEALTHY,
    )


def _validate_observation_binding(
    campaign: AttestationCampaign,
    fragment: UIContractFragment,
    observation: AttestationObservation,
) -> tuple[str, ...]:
    errors: list[str] = []
    if observation.contract_set_digest != campaign.contract_set_digest:
        errors.append("CONTRACT_SET_DIGEST_MISMATCH")
    if observation.campaign_id != campaign.campaign_id:
        errors.append("CAMPAIGN_ID_MISMATCH")
    if observation.fragment_version != fragment.fragment_version:
        errors.append("FRAGMENT_VERSION_MISMATCH")
    expected = tuple(fragment.selectors)
    observed = tuple(item.selector_key for item in observation.selector_observations)
    if observed != expected:
        errors.append("SELECTOR_SET_OR_ORDER_MISMATCH")
    return tuple(errors)


def _decision(
    fragment: UIContractFragment,
    observation: AttestationObservation,
    state: AttestationDecisionState,
    reasons: tuple[str, ...],
    lifecycle_state: UILifecycleState,
) -> AttestationDecision:
    record = CapabilityEvidenceRecord(
        fragment_id=fragment.fragment_id,
        fragment_version=fragment.fragment_version,
        scope=fragment.scope,
        application=fragment.application,
        surface=fragment.surface,
        contract_set_digest=observation.contract_set_digest,
        evidence_digest=observation.digest(),
        lifecycle_state=lifecycle_state,
        recorded_at=observation.observed_at,
    )
    return AttestationDecision(state=state, reasons=reasons, evidence_record=record)


def _fragment(contract_set: UIContractSet, fragment_id: str) -> UIContractFragment:
    matches = tuple(
        fragment for fragment in contract_set.fragments if fragment.fragment_id == fragment_id
    )
    if len(matches) != 1:
        raise ValueError("attestation references unknown contract fragment")
    return matches[0]


def _optional_bool(data: dict[str, Any], key: str) -> bool | None:
    value = data.get(key)
    if value is None:
        return None
    if not isinstance(value, bool):
        raise ValueError(f"{key} must be boolean when present")
    return value


def _canonical_json(payload: dict[str, object]) -> bytes:
    return json.dumps(
        payload,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def _format_timestamp(value: datetime) -> str:
    return value.astimezone(UTC).isoformat(timespec="microseconds").replace("+00:00", "Z")


__all__ = [
    "AttestationCampaign",
    "AttestationCampaignStep",
    "AttestationDecision",
    "AttestationDecisionState",
    "AttestationLevel",
    "AttestationObservation",
    "ObservationSource",
    "SelectorObservation",
    "SelectorObservationResult",
    "build_attestation_campaign",
    "evaluate_attestation_observation",
    "observation_from_dict",
]
