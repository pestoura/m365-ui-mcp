from __future__ import annotations

import pytest

from m365_mcp.application_registry import (
    ApplicationKey,
    ApplicationState,
    default_application_registry,
)
from m365_mcp.apps.outlook import readiness, sweep_mutations
from m365_mcp.idempotency_v2 import reserve_operation
from m365_mcp.state_identity import resource_state_identity
from m365_mcp.tool_registry import default_tool_registry
from m365_mcp.typed_locks import state_lock


def _ready() -> readiness.OutlookReadinessReport:
    return readiness.OutlookReadinessReport(
        state=readiness.OutlookReadinessState.DISCOVERY_READY,
        primary_context_verified=True,
        shared_context_verified=False,
        candidate_count=1,
        observed_count=1,
        blocked_count=0,
        reattestation_count=0,
    )


def test_sweep_discovery_and_safe_upsert_have_readback() -> None:
    rules = sweep_mutations.default_synthetic_sweeps()
    assert sweep_mutations.list_sweeps(readiness=_ready(), rules=rules) == rules

    replacement = sweep_mutations.SyntheticSweepRule(
        sweep_key="sweep-project",
        sender_key="person-alpha",
        mode=sweep_mutations.SweepMode.MOVE_CURRENT,
        target_folder_key="archive",
    )
    updated, result = sweep_mutations.manage_sweeps(
        rules,
        sweep_mutations.SweepMutationRequest(
            sweep_mutations.SweepMutationAction.UPSERT,
            "sweep-project",
            replacement,
        ),
        readiness=_ready(),
    )
    assert updated == (replacement,)
    assert result.changed is True
    assert result.verified is True
    assert result.read_back == replacement


def test_destructive_sweep_requires_explicit_allowance() -> None:
    destructive = sweep_mutations.SyntheticSweepRule(
        sweep_key="sweep-cleanup",
        sender_key="person-beta",
        mode=sweep_mutations.SweepMode.DELETE_OLDER_THAN_10_DAYS,
    )
    request = sweep_mutations.SweepMutationRequest(
        sweep_mutations.SweepMutationAction.UPSERT,
        "sweep-cleanup",
        destructive,
    )
    with pytest.raises(PermissionError, match="explicit policy allowance"):
        sweep_mutations.manage_sweeps((), request, readiness=_ready())

    updated, result = sweep_mutations.manage_sweeps(
        (),
        request,
        readiness=_ready(),
        allow_destructive=True,
    )
    assert updated == (destructive,)
    assert result.read_back is destructive


def test_sweep_request_binds_to_idempotency_and_lock() -> None:
    request = sweep_mutations.SweepMutationRequest(
        sweep_mutations.SweepMutationAction.DELETE,
        "sweep-project",
    )
    identity = resource_state_identity(
        ApplicationKey.OUTLOOK,
        account_scope="professional_session",
        container_kind="mail_settings",
        external_container_id="sweep",
        resource_kind="sweep_rule",
        external_resource_id=request.sweep_key,
    )
    record = reserve_operation(
        "outlook_sweep_manage",
        identity,
        request.to_payload(),
        read_back_required=True,
    )
    lock = state_lock("mock-professional-account", identity)
    assert record.read_back_required is True
    assert lock.state_identity_digest == identity.identity_digest


def test_out060_remains_reserved_and_not_public() -> None:
    outlook = default_application_registry().get(ApplicationKey.OUTLOOK)
    assert outlook.state is ApplicationState.RESERVED
    assert default_tool_registry().by_application("outlook") == ()
