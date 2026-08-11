from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest

from m365_browser_worker.account_context import AccountContext, AccountContextState
from m365_mcp.apps.outlook.live_read_acceptance import (
    OUTLOOK_READONLY_CAPABILITY,
    REL013_REQUIRED_GATE_IDS,
    build_outlook_readonly_live_evidence,
)
from m365_mcp.apps.outlook.mailbox_context import (
    PrimaryMailboxContext,
    PrimaryMailboxContextState,
)
from m365_mcp.attestation import (
    AttestationDecision,
    AttestationDecisionState,
    AttestationLevel,
    AttestationObservation,
    ObservationSource,
    SelectorObservation,
    SelectorObservationResult,
)
from m365_mcp.capability_evidence import CapabilityEvidenceRecord
from m365_mcp.capability_promotion import (
    LiveSupportState,
    PromotionAction,
    PromotionPolicy,
    evaluate_promotion,
)
from m365_mcp.capability_registry import default_capability_registry
from m365_mcp.ui_drift import UILifecycleState

CONTRACT_DIGEST = "sha256:" + "1" * 64
CAMPAIGN_DIGEST = "sha256:" + "2" * 64
STRUCTURAL_DIGEST = "sha256:" + "3" * 64
OBSERVED_AT = datetime(2026, 8, 11, 19, 30, tzinfo=UTC)


def _account() -> AccountContext:
    return AccountContext(
        state=AccountContextState.VERIFIED,
        professional=True,
        expected_profile=True,
    )


def _mailbox() -> PrimaryMailboxContext:
    return PrimaryMailboxContext(
        state=PrimaryMailboxContextState.VERIFIED,
        account_context_verified=True,
        primary_shell_verified=True,
        evidence_digest="4" * 64,
    )


def _observation(
    *,
    source: ObservationSource = ObservationSource.LIVE_UI,
    level: AttestationLevel = AttestationLevel.READ,
    mutation_applied: bool | None = None,
) -> AttestationObservation:
    return AttestationObservation(
        campaign_id=CAMPAIGN_DIGEST,
        contract_set_digest=CONTRACT_DIGEST,
        fragment_id="outlook.mail.read",
        fragment_version="1.0",
        target_level=level,
        source=source,
        observed_at=OBSERVED_AT,
        selector_observations=(
            SelectorObservation(
                selector_key="primary_mailbox_shell",
                result=SelectorObservationResult.UNIQUE_MATCH,
                structural_digest=STRUCTURAL_DIGEST,
            ),
        ),
        read_probe_ok=True,
        mutation_applied=mutation_applied,
    )


def _decision(observation: AttestationObservation) -> AttestationDecision:
    return AttestationDecision(
        state=AttestationDecisionState.PASSED,
        reasons=("READ_ATTESTATION_PASSED",),
        evidence_record=CapabilityEvidenceRecord(
            fragment_id=observation.fragment_id,
            fragment_version=observation.fragment_version,
            scope="application",
            application="outlook",
            surface=None,
            contract_set_digest=observation.contract_set_digest,
            evidence_digest=observation.digest(),
            lifecycle_state=UILifecycleState.HEALTHY,
            recorded_at=observation.observed_at,
        ),
    )


def _build(
    observation: AttestationObservation | None = None,
    *,
    account: AccountContext | None = None,
    mailbox: PrimaryMailboxContext | None = None,
    decision: AttestationDecision | None = None,
    gates: tuple[str, ...] = REL013_REQUIRED_GATE_IDS,
):
    current = observation or _observation()
    return build_outlook_readonly_live_evidence(
        account or _account(),
        mailbox or _mailbox(),
        current,
        decision or _decision(current),
        environment_id="professional-prod",
        passed_gate_ids=gates,
    )


def test_live_read_proof_builds_inert_rel025_evidence() -> None:
    evidence = _build()
    assert evidence.capability == OUTLOOK_READONLY_CAPABILITY
    assert evidence.acceptance_ok is True
    assert evidence.readback_ok is True
    assert evidence.contract_set_digest == CONTRACT_DIGEST


def test_mock_evidence_cannot_cross_rel013_boundary() -> None:
    observation = _observation(source=ObservationSource.MOCK)
    with pytest.raises(ValueError, match="REL013_LIVE_UI_EVIDENCE_REQUIRED"):
        _build(observation)


def test_wrong_tenant_or_account_context_fails_closed() -> None:
    account = AccountContext(
        state=AccountContextState.WRONG_TENANT,
        professional=True,
        expected_profile=False,
    )
    with pytest.raises(ValueError, match="REL013_ACCOUNT_CONTEXT_NOT_VERIFIED"):
        _build(account=account)


def test_ambiguous_mailbox_context_fails_closed() -> None:
    mailbox = PrimaryMailboxContext(
        state=PrimaryMailboxContextState.AMBIGUOUS,
        account_context_verified=True,
        primary_shell_verified=False,
    )
    with pytest.raises(ValueError, match="REL013_PRIMARY_MAILBOX_CONTEXT_NOT_VERIFIED"):
        _build(mailbox=mailbox)


def test_shared_mailbox_context_fails_closed() -> None:
    mailbox = PrimaryMailboxContext(
        state=PrimaryMailboxContextState.SHARED_MAILBOX_CONTEXT,
        account_context_verified=True,
        primary_shell_verified=False,
    )
    with pytest.raises(ValueError, match="REL013_PRIMARY_MAILBOX_CONTEXT_NOT_VERIFIED"):
        _build(mailbox=mailbox)


def test_mutation_attestation_is_rejected() -> None:
    observation = _observation(level=AttestationLevel.MUTATION, mutation_applied=True)
    with pytest.raises(ValueError, match="REL013_READ_ATTESTATION_REQUIRED"):
        _build(observation)


def test_missing_required_gate_fails_closed() -> None:
    gates = tuple(gate for gate in REL013_REQUIRED_GATE_IDS if gate != "REL-011")
    with pytest.raises(ValueError, match="REL013_REQUIRED_GATES_MISSING:REL-011"):
        _build(gates=gates)


def test_contract_digest_mismatch_fails_closed() -> None:
    observation = _observation()
    decision = _decision(observation)
    bad_record = replace(
        decision.evidence_record,
        contract_set_digest="sha256:" + "9" * 64,
    )
    with pytest.raises(ValueError, match="REL013_CONTRACT_SET_DIGEST_MISMATCH"):
        _build(observation, decision=replace(decision, evidence_record=bad_record))


def test_non_healthy_ui_lifecycle_fails_closed() -> None:
    observation = _observation()
    decision = _decision(observation)
    stale_record = replace(
        decision.evidence_record,
        lifecycle_state=UILifecycleState.RE_ATTESTATION_REQUIRED,
    )
    with pytest.raises(ValueError, match="REL013_UI_LIFECYCLE_NOT_HEALTHY"):
        _build(observation, decision=replace(decision, evidence_record=stale_record))


def test_rel013_evidence_still_requires_rel025_promotion_decision() -> None:
    evidence = _build()
    policy = PromotionPolicy(
        environment_id="professional-prod",
        current_contract_set_digest=CONTRACT_DIGEST,
        required_gate_ids=REL013_REQUIRED_GATE_IDS,
        max_age=timedelta(hours=1),
        dependencies_accepted=False,
    )
    result = evaluate_promotion(
        default_capability_registry(),
        evidence,
        policy,
        previous_state=LiveSupportState.LIVE_UNOBSERVED,
        now=OBSERVED_AT,
    )
    assert result.action is PromotionAction.HOLD
    assert result.target_state is LiveSupportState.LIVE_UNOBSERVED
