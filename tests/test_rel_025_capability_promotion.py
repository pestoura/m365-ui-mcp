from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from m365_mcp.capability_promotion import (
    LiveCapabilityEvidence,
    LiveSupportState,
    PromotionAction,
    PromotionEvidenceSource,
    PromotionPolicy,
    evaluate_promotion,
)
from m365_mcp.capability_registry import default_capability_registry

_DIGEST = "sha256:" + "a" * 64
_OTHER_DIGEST = "sha256:" + "b" * 64
_NOW = datetime(2026, 8, 11, 19, 0, tzinfo=UTC)
_GATES = ("REL-013", "policy", "egress", "selector", "readback")


def _evidence(**overrides: object) -> LiveCapabilityEvidence:
    values: dict[str, object] = {
        "application": "outlook",
        "surface": "outlook_web",
        "account_scope": "professional_session",
        "container_scope": "account",
        "capability": "mail.read",
        "environment_id": "tenant-test",
        "observed_at": _NOW - timedelta(minutes=5),
        "source": PromotionEvidenceSource.LIVE_UI,
        "contract_set_digest": _DIGEST,
        "passed_gate_ids": _GATES,
        "acceptance_ok": True,
        "readback_ok": True,
    }
    values.update(overrides)
    return LiveCapabilityEvidence(**values)  # type: ignore[arg-type]


def _policy(**overrides: object) -> PromotionPolicy:
    values: dict[str, object] = {
        "environment_id": "tenant-test",
        "current_contract_set_digest": _DIGEST,
        "required_gate_ids": _GATES,
        "max_age": timedelta(hours=1),
        "dependencies_accepted": True,
    }
    values.update(overrides)
    return PromotionPolicy(**values)  # type: ignore[arg-type]


def _decision(
    evidence: LiveCapabilityEvidence,
    policy: PromotionPolicy | None = None,
    *,
    previous_state: LiveSupportState = LiveSupportState.LIVE_UNOBSERVED,
):
    return evaluate_promotion(
        default_capability_registry(),
        evidence,
        policy or _policy(),
        previous_state=previous_state,
        now=_NOW,
    )


def test_valid_live_evidence_promotes_exact_reserved_outlook_capability() -> None:
    decision = _decision(_evidence())

    assert decision.action is PromotionAction.PROMOTE
    assert decision.target_state is LiveSupportState.SUPPORTED_LIVE
    assert decision.promotable is True
    assert decision.reasons == ("ALL_PROMOTION_EVIDENCE_VALID",)


@pytest.mark.parametrize("source", [PromotionEvidenceSource.MOCK, PromotionEvidenceSource.SYNTHETIC])
def test_mock_or_synthetic_evidence_never_promotes(source: PromotionEvidenceSource) -> None:
    decision = _decision(_evidence(source=source))

    assert decision.action is PromotionAction.HOLD
    assert decision.target_state is LiveSupportState.LIVE_UNOBSERVED
    assert decision.reasons == ("NON_LIVE_EVIDENCE_CANNOT_PROMOTE",)


def test_stale_live_evidence_requires_reattestation() -> None:
    decision = _decision(_evidence(observed_at=_NOW - timedelta(hours=2)))

    assert decision.action is PromotionAction.RE_ATTESTATION_REQUIRED
    assert decision.target_state is LiveSupportState.RE_ATTESTATION_REQUIRED
    assert decision.reasons == ("LIVE_EVIDENCE_STALE",)


def test_wrong_environment_scope_fails_closed() -> None:
    decision = _decision(_evidence(environment_id="other-tenant"))

    assert decision.action is PromotionAction.HOLD
    assert decision.reasons == ("ENVIRONMENT_SCOPE_MISMATCH",)


def test_wrong_capability_scope_fails_closed() -> None:
    decision = _decision(_evidence(container_scope="mailbox"))

    assert decision.action is PromotionAction.HOLD
    assert decision.reasons == ("CAPABILITY_SCOPE_NOT_DECLARED",)


def test_missing_required_gate_fails_closed() -> None:
    decision = _decision(_evidence(passed_gate_ids=_GATES[:-1]))

    assert decision.action is PromotionAction.HOLD
    assert decision.reasons == ("REQUIRED_GATE_MISSING:readback",)


def test_ui_contract_digest_drift_requires_reattestation() -> None:
    decision = _decision(_evidence(contract_set_digest=_OTHER_DIGEST))

    assert decision.action is PromotionAction.RE_ATTESTATION_REQUIRED
    assert decision.target_state is LiveSupportState.RE_ATTESTATION_REQUIRED
    assert decision.reasons == ("UI_CONTRACT_DIGEST_MISMATCH",)


def test_unmet_live_dependencies_hold_even_valid_evidence() -> None:
    decision = _decision(_evidence(), _policy(dependencies_accepted=False))

    assert decision.action is PromotionAction.HOLD
    assert decision.target_state is LiveSupportState.LIVE_UNOBSERVED
    assert decision.reasons == ("LIVE_ACCEPTANCE_DEPENDENCIES_UNMET",)


def test_missing_readback_fails_closed() -> None:
    decision = _decision(_evidence(readback_ok=False))

    assert decision.action is PromotionAction.HOLD
    assert decision.reasons == ("READBACK_NOT_CONFIRMED",)


def test_invalid_evidence_demotes_previous_supported_live_state() -> None:
    decision = _decision(
        _evidence(source=PromotionEvidenceSource.MOCK),
        previous_state=LiveSupportState.SUPPORTED_LIVE,
    )

    assert decision.action is PromotionAction.DEMOTE
    assert decision.target_state is LiveSupportState.RE_ATTESTATION_REQUIRED
    assert decision.reasons == ("NON_LIVE_EVIDENCE_CANNOT_PROMOTE",)


def test_contract_drift_demotes_previous_supported_live_state() -> None:
    decision = _decision(
        _evidence(contract_set_digest=_OTHER_DIGEST),
        previous_state=LiveSupportState.SUPPORTED_LIVE,
    )

    assert decision.action is PromotionAction.DEMOTE
    assert decision.target_state is LiveSupportState.RE_ATTESTATION_REQUIRED


def test_future_timestamp_requires_reattestation() -> None:
    decision = _decision(_evidence(observed_at=_NOW + timedelta(seconds=1)))

    assert decision.action is PromotionAction.RE_ATTESTATION_REQUIRED
    assert decision.reasons == ("EVIDENCE_TIMESTAMP_IN_FUTURE",)
