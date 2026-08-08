from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta

import pytest

from m365_mcp.approval_digest import ApprovalPlanDigest
from m365_mcp.approval_store import ApprovalConsumptionStatus, ApprovalStore


def _digest(value: str = "a" * 64) -> ApprovalPlanDigest:
    return ApprovalPlanDigest(
        schema_version="approval-plan-v1",
        algorithm="sha256",
        value=value,
        node_count=2,
    )


def test_approval_persists_across_store_reopen(tmp_path) -> None:
    database = tmp_path / "approvals.db"
    created = datetime(2026, 8, 8, 20, 0, tzinfo=UTC)
    approval_id = "approval_handle_0001"

    ApprovalStore(database).issue(
        _digest(),
        approval_id=approval_id,
        created_at=created,
    )
    result = ApprovalStore(database).consume(
        approval_id,
        _digest(),
        consumed_at=created + timedelta(seconds=1),
    )

    assert result.status is ApprovalConsumptionStatus.CONSUMED
    assert result.consumed is True


def test_approval_is_single_use_and_replay_safe(tmp_path) -> None:
    store = ApprovalStore(tmp_path / "approvals.db")
    created = datetime(2026, 8, 8, 20, 0, tzinfo=UTC)
    approval_id = "approval_handle_0002"
    store.issue(_digest(), approval_id=approval_id, created_at=created)

    first = store.consume(
        approval_id,
        _digest(),
        consumed_at=created + timedelta(seconds=1),
    )
    replay = store.consume(
        approval_id,
        _digest(),
        consumed_at=created + timedelta(seconds=2),
    )

    assert first.status is ApprovalConsumptionStatus.CONSUMED
    assert replay.status is ApprovalConsumptionStatus.ALREADY_CONSUMED
    assert replay.consumed_at == first.consumed_at


def test_digest_mismatch_never_consumes_approval(tmp_path) -> None:
    store = ApprovalStore(tmp_path / "approvals.db")
    created = datetime(2026, 8, 8, 20, 0, tzinfo=UTC)
    approval_id = "approval_handle_0003"
    store.issue(_digest(), approval_id=approval_id, created_at=created)

    mismatch = store.consume(
        approval_id,
        _digest("b" * 64),
        consumed_at=created + timedelta(seconds=1),
    )
    correct = store.consume(
        approval_id,
        _digest(),
        consumed_at=created + timedelta(seconds=2),
    )

    assert mismatch.status is ApprovalConsumptionStatus.DIGEST_MISMATCH
    assert correct.status is ApprovalConsumptionStatus.CONSUMED


def test_expired_approval_fails_closed_without_being_spent(tmp_path) -> None:
    store = ApprovalStore(tmp_path / "approvals.db")
    created = datetime(2026, 8, 8, 20, 0, tzinfo=UTC)
    approval_id = "approval_handle_0004"
    store.issue(
        _digest(),
        approval_id=approval_id,
        created_at=created,
        expires_at=created + timedelta(minutes=1),
    )

    result = store.consume(
        approval_id,
        _digest(),
        consumed_at=created + timedelta(minutes=2),
    )

    assert result.status is ApprovalConsumptionStatus.EXPIRED
    assert result.consumed is False


def test_two_concurrent_consumers_cannot_spend_same_approval(tmp_path) -> None:
    database = tmp_path / "approvals.db"
    store_a = ApprovalStore(database)
    store_b = ApprovalStore(database)
    created = datetime(2026, 8, 8, 20, 0, tzinfo=UTC)
    consumed_at = created + timedelta(seconds=1)
    approval_id = "approval_handle_0005"
    digest = _digest()
    store_a.issue(digest, approval_id=approval_id, created_at=created)

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = (
            executor.submit(store_a.consume, approval_id, digest, consumed_at=consumed_at),
            executor.submit(store_b.consume, approval_id, digest, consumed_at=consumed_at),
        )
        statuses = [future.result().status for future in futures]

    assert statuses.count(ApprovalConsumptionStatus.CONSUMED) == 1
    assert statuses.count(ApprovalConsumptionStatus.ALREADY_CONSUMED) == 1


def test_unknown_or_duplicate_approval_handles_fail_closed(tmp_path) -> None:
    store = ApprovalStore(tmp_path / "approvals.db")
    created = datetime(2026, 8, 8, 20, 0, tzinfo=UTC)
    approval_id = "approval_handle_0006"

    missing = store.consume(
        "approval_handle_9999",
        _digest(),
        consumed_at=created,
    )
    assert missing.status is ApprovalConsumptionStatus.NOT_FOUND

    store.issue(_digest(), approval_id=approval_id, created_at=created)
    with pytest.raises(ValueError, match="approval_id already exists"):
        store.issue(_digest(), approval_id=approval_id, created_at=created)


def test_approval_times_must_be_timezone_aware(tmp_path) -> None:
    store = ApprovalStore(tmp_path / "approvals.db")

    with pytest.raises(ValueError, match="created_at must be timezone-aware"):
        store.issue(
            _digest(),
            approval_id="approval_handle_0007",
            created_at=datetime(2026, 8, 8, 20, 0),
        )
