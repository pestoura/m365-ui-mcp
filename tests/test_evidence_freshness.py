"""CORE-020 evidence lifetime and revalidation policy tests."""

from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from m365_mcp.capability_evidence import CapabilityEvidenceRecord, CapabilityEvidenceStore
from m365_mcp.evidence_freshness import (
    EvidenceFreshnessReason,
    EvidenceLifetimePolicy,
    assess_contract_evidence_freshness,
    lifecycle_overlay_from_freshness,
    load_evidence_lifetime_policy,
)
from m365_mcp.ui_contract_store import UIContractFragment, UIContractSet
from m365_mcp.ui_drift import UILifecycleState


def _fragment(
    fragment_id: str,
    capability: str,
    *,
    selector: str,
) -> UIContractFragment:
    return UIContractFragment(
        fragment_id=fragment_id,
        fragment_version="0.1.0",
        scope="surface",
        application="planner",
        surface="planner-premium-web",
        capability_keys=(capability,),
        attested=True,
        attestation_status="ATTESTED",
        selectors={
            selector: {
                "value": "stable-placeholder",
                "status": "ATTESTED",
            }
        },
    )


def _contract_set() -> UIContractSet:
    return UIContractSet(
        "0.1.0",
        "0.1.0",
        (
            _fragment(
                "planner.plan-surface",
                "plans.read",
                selector="plan.card",
            ),
            _fragment(
                "planner.task-surface",
                "tasks.read",
                selector="task.list_container",
            ),
        ),
    )


def _record(
    contract_set: UIContractSet,
    fragment_id: str,
    *,
    state: UILifecycleState = UILifecycleState.HEALTHY,
    recorded_at: datetime,
) -> CapabilityEvidenceRecord:
    fragment = next(
        fragment
        for fragment in contract_set.fragments
        if fragment.fragment_id == fragment_id
    )
    return CapabilityEvidenceRecord(
        fragment_id=fragment.fragment_id,
        fragment_version=fragment.fragment_version,
        scope=fragment.scope,
        application=fragment.application,
        surface=fragment.surface,
        contract_set_digest=contract_set.digest(),
        evidence_digest=(
            "sha256:"
            "4d967f194d662474b4b03d670e17cc8ad36f8ca1c88f357e5712279e11af2a2d"
        ),
        lifecycle_state=state,
        recorded_at=recorded_at,
    )


def _policy(max_age_seconds: int = 604800) -> EvidenceLifetimePolicy:
    return EvidenceLifetimePolicy(
        schema_version="1.0.0",
        policy_id="ui-evidence-lifetime-v1",
        max_age_seconds=max_age_seconds,
        expiry_state=UILifecycleState.STALE,
        missing_evidence_state=UILifecycleState.RE_ATTESTATION_REQUIRED,
        future_timestamp_state=UILifecycleState.RE_ATTESTATION_REQUIRED,
    )


def test_default_policy_is_versioned_bounded_and_deterministic() -> None:
    policy = load_evidence_lifetime_policy()
    second = load_evidence_lifetime_policy()

    assert policy.schema_version == "1.0.0"
    assert policy.policy_id == "ui-evidence-lifetime-v1"
    assert policy.max_age_seconds == 604800
    assert policy.max_age == timedelta(days=7)
    assert policy.expiry_state is UILifecycleState.STALE
    assert policy.missing_evidence_state is UILifecycleState.RE_ATTESTATION_REQUIRED
    assert policy.future_timestamp_state is UILifecycleState.RE_ATTESTATION_REQUIRED
    assert policy.digest() == second.digest()
    assert policy.digest().startswith("sha256:")


@pytest.mark.parametrize(
    ("field", "state"),
    [
        ("expiry_state", UILifecycleState.HEALTHY),
        ("missing_evidence_state", UILifecycleState.HEALTHY),
        ("future_timestamp_state", UILifecycleState.HEALTHY),
        ("expiry_state", UILifecycleState.DRIFTED),
    ],
)
def test_policy_rejects_states_that_could_promote_or_misclassify_ageing(
    field: str,
    state: UILifecycleState,
) -> None:
    values: dict[str, object] = {
        "schema_version": "1.0.0",
        "policy_id": "ui-evidence-lifetime-v1",
        "max_age_seconds": 604800,
        "expiry_state": UILifecycleState.STALE,
        "missing_evidence_state": UILifecycleState.RE_ATTESTATION_REQUIRED,
        "future_timestamp_state": UILifecycleState.RE_ATTESTATION_REQUIRED,
    }
    values[field] = state

    with pytest.raises(ValueError, match="unsafe evidence lifetime"):
        EvidenceLifetimePolicy(**values)  # type: ignore[arg-type]


@pytest.mark.parametrize("seconds", [59, 2_592_001])
def test_policy_rejects_unbounded_age(seconds: int) -> None:
    with pytest.raises(ValueError, match="outside bounded range"):
        _policy(seconds)


def test_policy_loader_rejects_unknown_fields(tmp_path: Path) -> None:
    path = tmp_path / "policy.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": "1.0.0",
                "policy_id": "ui-evidence-lifetime-v1",
                "max_age_seconds": 604800,
                "expiry_state": "STALE",
                "missing_evidence_state": "RE_ATTESTATION_REQUIRED",
                "future_timestamp_state": "RE_ATTESTATION_REQUIRED",
                "grace_period_seconds": 999999,
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="closed schema"):
        load_evidence_lifetime_policy(path)


def test_fresh_healthy_evidence_remains_healthy() -> None:
    contract_set = _contract_set()
    now = datetime(2026, 8, 8, 16, 0, tzinfo=UTC)
    record = _record(
        contract_set,
        "planner.plan-surface",
        recorded_at=now - timedelta(days=1),
    )

    assessments = assess_contract_evidence_freshness(
        contract_set,
        (record,),
        policy=_policy(),
        now=now,
    )
    by_fragment = {item.fragment_id: item for item in assessments}

    assert by_fragment["planner.plan-surface"].effective_state is UILifecycleState.HEALTHY
    assert by_fragment["planner.plan-surface"].reason is EvidenceFreshnessReason.EVIDENCE_FRESH
    assert by_fragment["planner.plan-surface"].revalidation_required is False
    assert (
        by_fragment["planner.task-surface"].effective_state
        is UILifecycleState.RE_ATTESTATION_REQUIRED
    )
    assert (
        by_fragment["planner.task-surface"].reason
        is EvidenceFreshnessReason.EVIDENCE_MISSING
    )


def test_exact_expiry_threshold_becomes_stale() -> None:
    contract_set = _contract_set()
    recorded_at = datetime(2026, 8, 1, 16, 0, tzinfo=UTC)
    record = _record(
        contract_set,
        "planner.plan-surface",
        recorded_at=recorded_at,
    )

    assessment = assess_contract_evidence_freshness(
        contract_set,
        (record,),
        policy=_policy(),
        now=recorded_at + timedelta(days=7),
    )[0]

    assert assessment.effective_state is UILifecycleState.STALE
    assert assessment.reason is EvidenceFreshnessReason.EVIDENCE_EXPIRED
    assert assessment.expires_at == recorded_at + timedelta(days=7)
    assert assessment.revalidation_required is True


def test_future_timestamp_requires_reattestation() -> None:
    contract_set = _contract_set()
    now = datetime(2026, 8, 8, 16, 0, tzinfo=UTC)
    record = _record(
        contract_set,
        "planner.plan-surface",
        recorded_at=now + timedelta(seconds=1),
    )

    assessment = assess_contract_evidence_freshness(
        contract_set,
        (record,),
        policy=_policy(),
        now=now,
    )[0]

    assert assessment.effective_state is UILifecycleState.RE_ATTESTATION_REQUIRED
    assert assessment.reason is EvidenceFreshnessReason.EVIDENCE_TIMESTAMP_IN_FUTURE


@pytest.mark.parametrize(
    ("state", "reason"),
    [
        (UILifecycleState.STALE, EvidenceFreshnessReason.SOURCE_STALE),
        (UILifecycleState.DRIFTED, EvidenceFreshnessReason.SOURCE_DRIFTED),
        (
            UILifecycleState.RE_ATTESTATION_REQUIRED,
            EvidenceFreshnessReason.SOURCE_RE_ATTESTATION_REQUIRED,
        ),
    ],
)
def test_source_degradation_never_ages_back_to_healthy(
    state: UILifecycleState,
    reason: EvidenceFreshnessReason,
) -> None:
    contract_set = _contract_set()
    now = datetime(2026, 8, 8, 16, 0, tzinfo=UTC)
    record = _record(
        contract_set,
        "planner.plan-surface",
        state=state,
        recorded_at=now - timedelta(seconds=1),
    )

    assessment = assess_contract_evidence_freshness(
        contract_set,
        (record,),
        policy=_policy(),
        now=now,
    )[0]

    assert assessment.effective_state is state
    assert assessment.reason is reason
    assert assessment.revalidation_required is True


def test_wrong_contract_binding_and_duplicate_records_are_rejected() -> None:
    contract_set = _contract_set()
    now = datetime(2026, 8, 8, 16, 0, tzinfo=UTC)
    valid = _record(
        contract_set,
        "planner.plan-surface",
        recorded_at=now,
    )
    other_contract = UIContractSet("0.2.0", contract_set.legacy_version, contract_set.fragments)

    with pytest.raises(ValueError, match="contract-set digest mismatch"):
        assess_contract_evidence_freshness(
            other_contract,
            (valid,),
            policy=_policy(),
            now=now,
        )

    with pytest.raises(ValueError, match="duplicate fragment records"):
        assess_contract_evidence_freshness(
            contract_set,
            (valid, valid),
            policy=_policy(),
            now=now,
        )


def test_stale_fragment_degrades_only_dependent_capability() -> None:
    contract_set = _contract_set()
    now = datetime(2026, 8, 8, 16, 0, tzinfo=UTC)
    plan_record = _record(
        contract_set,
        "planner.plan-surface",
        recorded_at=now - timedelta(days=1),
    )
    task_record = _record(
        contract_set,
        "planner.task-surface",
        recorded_at=now - timedelta(days=8),
    )

    overlay = lifecycle_overlay_from_freshness(
        assess_contract_evidence_freshness(
            contract_set,
            (plan_record, task_record),
            policy=_policy(),
            now=now,
        )
    )
    plans = contract_set.attestation_for_capability(
        "planner",
        "plans.read",
        lifecycle_by_fragment=overlay,
    )
    tasks = contract_set.attestation_for_capability(
        "planner",
        "tasks.read",
        lifecycle_by_fragment=overlay,
    )

    assert plans.attested is True
    assert plans.stale is False
    assert tasks.attested is False
    assert tasks.stale is True
    assert tasks.reasons == ("UI_FRAGMENT_STALE:planner.task-surface",)


def test_store_latest_records_feed_freshness_without_mutating_history(tmp_path: Path) -> None:
    contract_set = _contract_set()
    now = datetime(2026, 8, 8, 16, 0, tzinfo=UTC)
    state_path = tmp_path / "evidence.db"
    store = CapabilityEvidenceStore(state_path)
    old_record = _record(
        contract_set,
        "planner.plan-surface",
        recorded_at=now - timedelta(days=8),
    )
    new_record = _record(
        contract_set,
        "planner.plan-surface",
        recorded_at=now - timedelta(hours=1),
    )
    store.append(old_record, contract_set=contract_set)
    store.append(new_record, contract_set=contract_set)

    assessments = assess_contract_evidence_freshness(
        contract_set,
        store.latest_records(contract_set),
        policy=_policy(),
        now=now,
    )

    assert assessments[0].effective_state is UILifecycleState.HEALTHY
    assert assessments[0].evidence_id == new_record.evidence_id

    with sqlite3.connect(state_path) as conn:
        row_count = conn.execute("SELECT COUNT(*) FROM capability_ui_evidence").fetchone()[0]
    assert row_count == 2
