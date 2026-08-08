"""CORE-018 sanitized capability evidence persistence tests."""

from __future__ import annotations

import hashlib
import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from m365_mcp.capability_evidence import CapabilityEvidenceRecord, CapabilityEvidenceStore
from m365_mcp.ui_contract_store import UIContractFragment, UIContractSet
from m365_mcp.ui_drift import UILifecycleState


def _digest(value: str) -> str:
    return f"sha256:{hashlib.sha256(value.encode('utf-8')).hexdigest()}"


def _contract_set(*, set_version: str = "0.1.0") -> UIContractSet:
    fragment = UIContractFragment(
        fragment_id="planner.task-surface",
        fragment_version="0.1.0",
        scope="surface",
        application="planner",
        surface="planner-premium-web",
        capability_keys=("tasks.read",),
        attested=True,
        attestation_status="ATTESTED",
        selectors={
            "planner.task.selector": {
                "value": "stable",
                "status": "ATTESTED",
            }
        },
    )
    return UIContractSet(set_version, "0.1.0", (fragment,))


def _record(
    contract_set: UIContractSet,
    *,
    state: UILifecycleState = UILifecycleState.HEALTHY,
    recorded_at: datetime | None = None,
    evidence_digest: str | None = None,
) -> CapabilityEvidenceRecord:
    fragment = contract_set.fragments[0]
    return CapabilityEvidenceRecord(
        fragment_id=fragment.fragment_id,
        fragment_version=fragment.fragment_version,
        scope=fragment.scope,
        application=fragment.application,
        surface=fragment.surface,
        contract_set_digest=contract_set.digest(),
        evidence_digest=evidence_digest or _digest("sanitized-attestation-evidence"),
        lifecycle_state=state,
        recorded_at=recorded_at or datetime(2026, 8, 8, 15, 30, tzinfo=UTC),
    )


def test_append_round_trip_is_idempotent_and_digest_bound(state_path: Path) -> None:
    contract_set = _contract_set()
    store = CapabilityEvidenceStore(state_path)
    record = _record(contract_set)

    first_id = store.append(record, contract_set=contract_set)
    second_id = store.append(record, contract_set=contract_set)

    assert first_id == second_id == record.evidence_id
    assert store.latest_records(contract_set) == (record,)
    assert store.lifecycle_overlay(contract_set) == {
        "planner.task-surface": UILifecycleState.HEALTHY
    }

    with sqlite3.connect(state_path) as conn:
        count = conn.execute("SELECT COUNT(*) FROM capability_ui_evidence").fetchone()[0]
    assert count == 1


def test_latest_record_uses_evidence_timestamp_not_append_order(state_path: Path) -> None:
    contract_set = _contract_set()
    store = CapabilityEvidenceStore(state_path)
    newer = _record(
        contract_set,
        state=UILifecycleState.DRIFTED,
        recorded_at=datetime(2026, 8, 8, 16, 0, tzinfo=UTC),
        evidence_digest=_digest("newer"),
    )
    older = _record(
        contract_set,
        state=UILifecycleState.STALE,
        recorded_at=newer.recorded_at - timedelta(hours=1),
        evidence_digest=_digest("older"),
    )

    store.append(newer, contract_set=contract_set)
    store.append(older, contract_set=contract_set)

    assert store.lifecycle_overlay(contract_set) == {
        "planner.task-surface": UILifecycleState.DRIFTED
    }


def test_evidence_for_previous_contract_set_is_not_projected(state_path: Path) -> None:
    old_contract = _contract_set(set_version="0.1.0")
    current_contract = _contract_set(set_version="0.2.0")
    store = CapabilityEvidenceStore(state_path)
    store.append(
        _record(old_contract, state=UILifecycleState.DRIFTED),
        contract_set=old_contract,
    )

    assert old_contract.digest() != current_contract.digest()
    assert store.latest_records(current_contract) == ()
    assert store.lifecycle_overlay(current_contract) == {}


def test_append_rejects_contract_or_fragment_metadata_mismatch(state_path: Path) -> None:
    contract_set = _contract_set()
    store = CapabilityEvidenceStore(state_path)
    record = _record(contract_set)
    wrong_contract = _contract_set(set_version="0.2.0")

    with pytest.raises(ValueError, match="contract-set digest mismatch"):
        store.append(record, contract_set=wrong_contract)

    mismatched = CapabilityEvidenceRecord(
        fragment_id=record.fragment_id,
        fragment_version="9.9.9",
        scope=record.scope,
        application=record.application,
        surface=record.surface,
        contract_set_digest=record.contract_set_digest,
        evidence_digest=record.evidence_digest,
        lifecycle_state=record.lifecycle_state,
        recorded_at=record.recorded_at,
    )
    with pytest.raises(ValueError, match="fragment metadata mismatch"):
        store.append(mismatched, contract_set=contract_set)


def test_record_rejects_unbounded_or_unsafe_metadata() -> None:
    contract_set = _contract_set()
    record = _record(contract_set)

    with pytest.raises(ValueError, match="evidence digest"):
        CapabilityEvidenceRecord(
            fragment_id=record.fragment_id,
            fragment_version=record.fragment_version,
            scope=record.scope,
            application=record.application,
            surface=record.surface,
            contract_set_digest=record.contract_set_digest,
            evidence_digest="mail subject: confidential tenant content",
            lifecycle_state=record.lifecycle_state,
            recorded_at=record.recorded_at,
        )

    with pytest.raises(ValueError, match="timezone-aware"):
        CapabilityEvidenceRecord(
            fragment_id=record.fragment_id,
            fragment_version=record.fragment_version,
            scope=record.scope,
            application=record.application,
            surface=record.surface,
            contract_set_digest=record.contract_set_digest,
            evidence_digest=record.evidence_digest,
            lifecycle_state=record.lifecycle_state,
            recorded_at=datetime(2026, 8, 8, 15, 30),
        )


def test_persistence_schema_has_no_raw_tenant_content_fields(state_path: Path) -> None:
    store = CapabilityEvidenceStore(state_path)
    store.initialise()
    with sqlite3.connect(state_path) as conn:
        columns = {
            row[1]
            for row in conn.execute("PRAGMA table_info(capability_ui_evidence)").fetchall()
        }

    assert columns == {
        "sequence",
        "evidence_id",
        "fragment_id",
        "fragment_version",
        "scope",
        "application",
        "surface",
        "contract_set_digest",
        "evidence_digest",
        "lifecycle_state",
        "recorded_at",
    }
    assert not columns & {
        "payload",
        "content",
        "url",
        "account_id",
        "container_id",
        "cookie",
        "token",
        "screenshot",
        "storage_state",
    }
