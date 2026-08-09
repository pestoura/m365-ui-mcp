from datetime import UTC, datetime, timedelta

import pytest

from m365_mcp import application_registry, execution_provenance, policy, security_tiers

START = datetime(2026, 8, 8, 20, 0, tzinfo=UTC)


def _provenance(
    mode: execution_provenance.ExecutionMode = execution_provenance.ExecutionMode.MOCK,
    *,
    evidence_reference_ids: tuple[str, ...] = (),
) -> execution_provenance.ExecutionProvenance:
    return execution_provenance.make_execution_provenance(
        operation_id="raw-operation-id",
        application=application_registry.ApplicationKey.PLANNER,
        tool_name="planner_plan_list",
        tool_version="0.1.0",
        mode=mode,
        policy_decision=policy.Decision.ALLOW,
        security_tier=security_tiers.SecurityTier.T2,
        started_at=START,
        completed_at=START + timedelta(milliseconds=1250),
        evidence_reference_ids=evidence_reference_ids,
    )


def test_provenance_hashes_raw_operation_id_and_projects_bounded_context() -> None:
    provenance = _provenance()
    projection = provenance.to_projection()

    assert len(provenance.operation_id_digest) == 64
    assert "raw-operation-id" not in repr(provenance)
    assert projection["application"] == "planner"
    assert projection["tool_name"] == "planner_plan_list"
    assert projection["mode"] == "MOCK"
    assert projection["policy_decision"] == "ALLOW"
    assert projection["security_tier"] == "T2"
    assert projection["duration_ms"] == 1250
    assert len(provenance.provenance_digest) == 64


def test_live_provenance_requires_evidence_reference() -> None:
    with pytest.raises(ValueError, match="LIVE provenance requires"):
        _provenance(execution_provenance.ExecutionMode.LIVE)

    live = _provenance(
        execution_provenance.ExecutionMode.LIVE,
        evidence_reference_ids=("a" * 64,),
    )
    assert live.mode is execution_provenance.ExecutionMode.LIVE
    assert live.evidence_reference_ids == ("a" * 64,)


def test_state_and_checkpoint_digests_are_optional_but_validated() -> None:
    provenance = execution_provenance.make_execution_provenance(
        operation_id="operation-a",
        application=application_registry.ApplicationKey.PLANNER,
        tool_name="planner_plan_list",
        tool_version="0.1.0",
        mode=execution_provenance.ExecutionMode.MOCK,
        policy_decision=policy.Decision.ALLOW,
        security_tier=security_tiers.SecurityTier.T2,
        started_at=START,
        completed_at=START,
        state_identity_digest="b" * 64,
        checkpoint_digest="c" * 64,
    )

    projection = provenance.to_projection()
    assert projection["state_identity_digest"] == "b" * 64
    assert projection["checkpoint_digest"] == "c" * 64


def test_provenance_rejects_invalid_time_and_duplicate_evidence() -> None:
    with pytest.raises(ValueError, match="completed_at must not precede"):
        execution_provenance.make_execution_provenance(
            operation_id="operation-a",
            application=application_registry.ApplicationKey.PLANNER,
            tool_name="planner_health",
            tool_version="0.1.0",
            mode=execution_provenance.ExecutionMode.MOCK,
            policy_decision=policy.Decision.ALLOW,
            security_tier=security_tiers.SecurityTier.T0,
            started_at=START,
            completed_at=START - timedelta(seconds=1),
        )

    with pytest.raises(ValueError, match="evidence_reference_ids must be unique"):
        _provenance(
            evidence_reference_ids=("a" * 64, "a" * 64),
        )


def test_provenance_requires_timezone_aware_timestamps() -> None:
    naive = datetime(2026, 8, 8, 20, 0)
    with pytest.raises(ValueError, match="started_at must be timezone-aware"):
        execution_provenance.make_execution_provenance(
            operation_id="operation-a",
            application=application_registry.ApplicationKey.PLANNER,
            tool_name="planner_health",
            tool_version="0.1.0",
            mode=execution_provenance.ExecutionMode.MOCK,
            policy_decision=policy.Decision.ALLOW,
            security_tier=security_tiers.SecurityTier.T0,
            started_at=naive,
            completed_at=START,
        )


def test_provenance_digest_changes_with_semantic_execution_context() -> None:
    first = _provenance()
    second = execution_provenance.make_execution_provenance(
        operation_id="raw-operation-id",
        application=application_registry.ApplicationKey.PLANNER,
        tool_name="planner_task_list",
        tool_version="0.1.0",
        mode=execution_provenance.ExecutionMode.MOCK,
        policy_decision=policy.Decision.ALLOW,
        security_tier=security_tiers.SecurityTier.T2,
        started_at=START,
        completed_at=START + timedelta(milliseconds=1250),
    )

    assert first.provenance_digest != second.provenance_digest
