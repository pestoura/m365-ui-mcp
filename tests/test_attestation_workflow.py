"""CORE-019 deterministic UI attestation workflow tests."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from pathlib import Path

import pytest

from m365_mcp.attestation import (
    AttestationDecisionState,
    AttestationLevel,
    AttestationObservation,
    ObservationSource,
    SelectorObservation,
    SelectorObservationResult,
    build_attestation_campaign,
    evaluate_attestation_observation,
    observation_from_dict,
)
from m365_mcp.capability_evidence import CapabilityEvidenceStore
from m365_mcp.ui_contract_store import UIContractFragment, UIContractSet
from m365_mcp.ui_drift import UILifecycleState


def _digest(value: str) -> str:
    return f"sha256:{hashlib.sha256(value.encode('utf-8')).hexdigest()}"


def _contract(*, attested: bool, with_locator: bool = True) -> UIContractSet:
    metadata: dict[str, object] = {
        "value": None,
        "status": "ATTESTED" if attested else "UNVERIFIED_LIVE",
    }
    if with_locator:
        metadata["locators"] = [
            {
                "strategy": "role",
                "value": "button",
                "name": "Task list",
            }
        ]
    fragment = UIContractFragment(
        fragment_id="planner.task-surface",
        fragment_version="0.1.0",
        scope="surface",
        application="planner",
        surface="planner-premium-web",
        capability_keys=("tasks.read",),
        attested=attested,
        attestation_status="ATTESTED" if attested else "UNVERIFIED_LIVE",
        selectors={"task.list_container": metadata},
    )
    return UIContractSet("0.1.0", "0.1.0", (fragment,))


def _observation(
    contract_set: UIContractSet,
    *,
    level: AttestationLevel,
    source: ObservationSource = ObservationSource.LIVE_UI,
    result: SelectorObservationResult = SelectorObservationResult.UNIQUE_MATCH,
    read_probe_ok: bool | None = None,
    mutation_applied: bool | None = None,
    read_back_ok: bool | None = None,
    compensation_proven: bool | None = None,
    approval_digest: str | None = None,
) -> AttestationObservation:
    fragment = contract_set.fragments[0]
    campaign = build_attestation_campaign(
        contract_set,
        level,
        fragment_ids=(fragment.fragment_id,),
    )
    return AttestationObservation(
        campaign_id=campaign.campaign_id,
        contract_set_digest=contract_set.digest(),
        fragment_id=fragment.fragment_id,
        fragment_version=fragment.fragment_version,
        target_level=level,
        source=source,
        observed_at=datetime(2026, 8, 8, 16, 0, tzinfo=UTC),
        selector_observations=(
            SelectorObservation(
                selector_key="task.list_container",
                result=result,
                structural_digest=(
                    _digest("sanitized-shape")
                    if result is SelectorObservationResult.UNIQUE_MATCH
                    else None
                ),
            ),
        ),
        locale="pt-PT",
        ui_surface_signal_digest=_digest("ui-surface-signal"),
        read_probe_ok=read_probe_ok,
        mutation_applied=mutation_applied,
        read_back_ok=read_back_ok,
        compensation_proven=compensation_proven,
        approval_digest=approval_digest,
    )


def test_campaign_is_deterministic_and_does_not_expose_locator_values() -> None:
    contract_set = _contract(attested=True)

    first = build_attestation_campaign(contract_set, AttestationLevel.UI)
    second = build_attestation_campaign(contract_set, AttestationLevel.UI)

    assert first.campaign_id == second.campaign_id
    assert first.to_dict() == second.to_dict()
    encoded = str(first.to_dict())
    assert "Task list" not in encoded
    assert '"button"' not in encoded
    assert first.steps[0].locator_strategies == ("role",)
    assert first.steps[0].discovery_required is False


def test_mock_evidence_never_promotes_live_state() -> None:
    contract_set = _contract(attested=True)
    observation = _observation(
        contract_set,
        level=AttestationLevel.UI,
        source=ObservationSource.MOCK,
    )

    decision = evaluate_attestation_observation(contract_set, observation)

    assert decision.state is AttestationDecisionState.REVIEW_REQUIRED
    assert decision.reasons == ("NON_LIVE_EVIDENCE_CANNOT_PROMOTE",)
    assert decision.evidence_record.lifecycle_state is UILifecycleState.RE_ATTESTATION_REQUIRED


def test_discovery_evidence_requires_review_and_cannot_mark_healthy() -> None:
    contract_set = _contract(attested=False, with_locator=False)
    observation = _observation(contract_set, level=AttestationLevel.DISCOVERY)

    decision = evaluate_attestation_observation(contract_set, observation)

    assert decision.state is AttestationDecisionState.REVIEW_REQUIRED
    assert decision.reasons == (
        "DISCOVERY_EVIDENCE_RECORDED_CONTRACT_REVIEW_REQUIRED",
    )
    assert decision.evidence_record.lifecycle_state is UILifecycleState.RE_ATTESTATION_REQUIRED


def test_ui_attestation_requires_declared_locator_before_promotion() -> None:
    contract_set = _contract(attested=False, with_locator=False)
    observation = _observation(contract_set, level=AttestationLevel.UI)

    decision = evaluate_attestation_observation(contract_set, observation)

    assert decision.state is AttestationDecisionState.REVIEW_REQUIRED
    assert decision.reasons == (
        "LOCATOR_DISCOVERY_REQUIRED:task.list_container",
    )


def test_attested_fragment_live_ui_observation_passes_healthy() -> None:
    contract_set = _contract(attested=True)
    observation = _observation(contract_set, level=AttestationLevel.UI)

    decision = evaluate_attestation_observation(contract_set, observation)

    assert decision.state is AttestationDecisionState.PASSED
    assert decision.reasons == ("UI_ATTESTATION_PASSED",)
    assert decision.evidence_record.lifecycle_state is UILifecycleState.HEALTHY
    assert decision.evidence_record.evidence_digest == observation.digest()


def test_selector_contradiction_marks_attested_fragment_drifted() -> None:
    contract_set = _contract(attested=True)
    observation = _observation(
        contract_set,
        level=AttestationLevel.UI,
        result=SelectorObservationResult.AMBIGUOUS,
    )

    decision = evaluate_attestation_observation(contract_set, observation)

    assert decision.state is AttestationDecisionState.FAILED
    assert decision.reasons == ("SELECTOR_AMBIGUOUS:task.list_container",)
    assert decision.evidence_record.lifecycle_state is UILifecycleState.DRIFTED


def test_read_attestation_requires_semantic_probe_confirmation() -> None:
    contract_set = _contract(attested=True)
    failed = _observation(contract_set, level=AttestationLevel.READ, read_probe_ok=False)
    passed = _observation(contract_set, level=AttestationLevel.READ, read_probe_ok=True)

    failed_decision = evaluate_attestation_observation(contract_set, failed)
    passed_decision = evaluate_attestation_observation(contract_set, passed)

    assert failed_decision.state is AttestationDecisionState.FAILED
    assert failed_decision.reasons == ("READ_PROBE_NOT_CONFIRMED",)
    assert passed_decision.state is AttestationDecisionState.PASSED
    assert passed_decision.reasons == ("READ_ATTESTATION_PASSED",)


def test_mutation_attestation_requires_approval_readback_and_compensation() -> None:
    contract_set = _contract(attested=True)
    incomplete = _observation(
        contract_set,
        level=AttestationLevel.MUTATION,
        read_probe_ok=True,
        mutation_applied=True,
        read_back_ok=True,
        compensation_proven=False,
        approval_digest=_digest("approval"),
    )
    complete = _observation(
        contract_set,
        level=AttestationLevel.MUTATION,
        read_probe_ok=True,
        mutation_applied=True,
        read_back_ok=True,
        compensation_proven=True,
        approval_digest=_digest("approval"),
    )

    incomplete_decision = evaluate_attestation_observation(contract_set, incomplete)
    complete_decision = evaluate_attestation_observation(contract_set, complete)

    assert incomplete_decision.state is AttestationDecisionState.FAILED
    assert incomplete_decision.reasons == ("MUTATION_COMPENSATION_NOT_PROVEN",)
    assert complete_decision.state is AttestationDecisionState.PASSED
    assert complete_decision.reasons == ("MUTATION_ATTESTATION_PASSED",)


def test_observation_parser_rejects_raw_or_unknown_evidence_fields() -> None:
    contract_set = _contract(attested=True)
    observation = _observation(contract_set, level=AttestationLevel.UI)
    raw = observation.canonical_payload()
    raw["screenshot"] = "authenticated.png"

    with pytest.raises(ValueError, match="unknown fields"):
        observation_from_dict(raw)


def test_decision_integrates_with_core_018_evidence_store(tmp_path: Path) -> None:
    contract_set = _contract(attested=True)
    observation = _observation(contract_set, level=AttestationLevel.UI)
    decision = evaluate_attestation_observation(contract_set, observation)
    store = CapabilityEvidenceStore(tmp_path / "evidence.db")

    evidence_id = store.append(decision.evidence_record, contract_set=contract_set)

    assert evidence_id == decision.evidence_record.evidence_id
    assert store.lifecycle_overlay(contract_set) == {
        "planner.task-surface": UILifecycleState.HEALTHY
    }
