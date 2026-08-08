"""Tests for contract manifests and the non-negotiable product invariants."""

from __future__ import annotations

import pytest

from planner_mcp import CONTRACT_VERSION, PRODUCT_VERSION, SCHEMA_VERSION
from planner_mcp.contracts import (
    AgentCard,
    CapabilityEntry,
    CapabilityManifest,
    ContractError,
    ExtendedToolManifest,
    ToolManifest,
)
from planner_mcp.enums import (
    ApprovalRequirement,
    AttestationStatus,
    CapabilityState,
    IdempotencyClass,
    MutationClass,
    TrustLevel,
)
from planner_mcp.tool_catalog import CATALOG_0_1_0


def test_versions_are_0_1_0() -> None:
    assert CONTRACT_VERSION == PRODUCT_VERSION == SCHEMA_VERSION == "0.1.0"


def test_graph_is_never_a_functional_gate() -> None:
    assert AgentCard().graph_is_functional_gate is False
    assert CapabilityManifest().graph_is_functional_gate is False
    with pytest.raises(ContractError):
        CapabilityManifest(graph_is_functional_gate=True)
    with pytest.raises(ContractError):
        AgentCard(graph_is_functional_gate=True)


def test_agent_card_declares_boundaries() -> None:
    card = AgentCard()
    assert card.mfa_channel == "microsoft-authenticator-only"
    assert card.human_in_the_loop is True
    assert "ui_drift" in card.fails_closed_on
    assert "conditional_access_blocker" in card.fails_closed_on
    assert any("mfa" in item for item in card.never_does)
    assert any("password" in item for item in card.never_does)


def test_agent_card_rejects_other_mfa_channels() -> None:
    with pytest.raises(ContractError):
        AgentCard(mfa_channel="telegram")


def test_capability_entries_default_to_unverified() -> None:
    entry = CapabilityEntry(capability="dependencies", domain="scheduling")
    assert entry.state is CapabilityState.UNVERIFIED_LIVE
    assert entry.read_validated is False
    assert entry.mutation_validated is False
    assert entry.required_mutation_class is MutationClass.READ
    assert entry.drift_behavior == "FAIL_CLOSED"


def test_capability_state_requires_evidence() -> None:
    with pytest.raises(ContractError):
        CapabilityEntry(
            capability="buckets",
            domain="structure",
            state=CapabilityState.SUPPORTED,
        )
    ok = CapabilityEntry(
        capability="buckets",
        domain="structure",
        state=CapabilityState.SUPPORTED,
        evidence_refs=("evidence/ui/buckets.json",),
    )
    assert ok.state is CapabilityState.SUPPORTED


def test_manifest_accepts_the_catalog() -> None:
    manifest = CapabilityManifest(tools=CATALOG_0_1_0)
    assert len(manifest.tools) == len(CATALOG_0_1_0)
    assert manifest.supported() == ()


def test_manifest_rejects_duplicate_tools() -> None:
    with pytest.raises(ContractError):
        CapabilityManifest(tools=(CATALOG_0_1_0[0], CATALOG_0_1_0[0]))


def test_tool_name_pattern_is_enforced() -> None:
    with pytest.raises(ContractError):
        ToolManifest(
            name="click",
            title="Click",
            description="generic",
            mutation_class=MutationClass.READ,
        )


def test_governed_write_cannot_skip_approval() -> None:
    with pytest.raises(ContractError):
        ExtendedToolManifest(
            name="planner_task_delete",
            title="Delete task",
            description="destructive",
            trust_level=TrustLevel.TENANT_WRITE,
            mutation_class=MutationClass.DESTRUCTIVE,
            reversible=False,
            idempotency_class=IdempotencyClass.NON_IDEMPOTENT,
            approval_requirement=ApprovalRequirement.NONE,
            attestation_status=AttestationStatus.UNVERIFIED_LIVE,
            policy_rule_id="POL-X",
        )


def test_drift_behavior_must_be_fail_closed() -> None:
    with pytest.raises(ContractError):
        ExtendedToolManifest(
            name="planner_plan_list",
            title="List plans",
            description="read",
            trust_level=TrustLevel.TENANT_READ,
            mutation_class=MutationClass.READ,
            reversible=True,
            idempotency_class=IdempotencyClass.PURE_READ,
            approval_requirement=ApprovalRequirement.NONE,
            attestation_status=AttestationStatus.UNVERIFIED_LIVE,
            policy_rule_id="POL-READ-TENANT",
            drift_behavior="BEST_EFFORT",
        )
