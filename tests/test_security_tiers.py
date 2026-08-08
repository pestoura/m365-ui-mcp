from __future__ import annotations

from m365_mcp.config import Settings
from m365_mcp.policy import Decision, MetadataPolicyEngine
from m365_mcp.security_tiers import SecurityTier, classify_security_tier
from m365_mcp.tool_registry import (
    CompatibilityRequirement,
    ImplementationState,
    MutationClass,
    ToolDefinition,
    ToolRegistry,
)


def _definition(
    name: str,
    *,
    mutation_class: MutationClass = MutationClass.READ,
    risk_class: str = "READ_ONLY",
    approval_requirement: str = "none",
) -> ToolDefinition:
    return ToolDefinition(
        name=name,
        version="0.1.0",
        application="planner",
        surface="test",
        domain="test",
        input_schema={
            "type": "object",
            "properties": {},
            "required": [],
            "additionalProperties": False,
        },
        output_schema={"type": "object", "properties": {}, "additionalProperties": False},
        mutation_class=mutation_class,
        risk_class=risk_class,
        implementation_state=ImplementationState.SPECIFIED_ONLY,
        capability_keys=(),
        ui_contract_dependencies=(),
        read_back_strategy="TEST",
        idempotency_semantics="TEST",
        approval_requirement=approval_requirement,
        compatibility_requirement=CompatibilityRequirement.INTERNAL_ONLY,
    )


def test_closed_security_tier_order_is_stable() -> None:
    assert tuple(SecurityTier) == (
        SecurityTier.T0,
        SecurityTier.T1,
        SecurityTier.T2,
        SecurityTier.T3,
        SecurityTier.T4,
    )
    assert (
        SecurityTier.T0
        < SecurityTier.T1
        < SecurityTier.T2
        < SecurityTier.T3
        < SecurityTier.T4
    )


def test_read_risk_metadata_maps_to_t0_t1_t2() -> None:
    assert classify_security_tier(_definition("planner_t0")).tier is SecurityTier.T0
    assert (
        classify_security_tier(
            _definition("planner_t1", risk_class="ACCOUNT_CONTEXT_READ")
        ).tier
        is SecurityTier.T1
    )
    assert (
        classify_security_tier(
            _definition("planner_t2", risk_class="M365_CONTENT_READ")
        ).tier
        is SecurityTier.T2
    )


def test_mutation_class_dominates_read_risk_metadata() -> None:
    assert (
        classify_security_tier(
            _definition("planner_update", mutation_class=MutationClass.UPDATE)
        ).tier
        is SecurityTier.T3
    )
    assert (
        classify_security_tier(
            _definition("planner_delete", mutation_class=MutationClass.DELETE)
        ).tier
        is SecurityTier.T4
    )
    assert (
        classify_security_tier(
            _definition("planner_high", mutation_class=MutationClass.HIGH_IMPACT)
        ).tier
        is SecurityTier.T4
    )


def test_unknown_read_risk_fails_closed_to_t4() -> None:
    assessment = classify_security_tier(
        _definition("planner_unknown", risk_class="FUTURE_UNREVIEWED_RISK")
    )
    assert assessment.tier is SecurityTier.T4
    assert assessment.reason == "UNCLASSIFIED_RISK_FAIL_CLOSED"


def test_policy_projects_tier_without_weakening_existing_decision() -> None:
    read = _definition("planner_content", risk_class="M365_CONTENT_READ")
    unknown = _definition("planner_unknown", risk_class="FUTURE_UNREVIEWED_RISK")
    engine = MetadataPolicyEngine(ToolRegistry((read, unknown)))

    read_result = engine.evaluate("planner_content", Settings())
    assert read_result.decision is Decision.ALLOW
    assert read_result.security_tier is SecurityTier.T2

    unknown_result = engine.evaluate("planner_unknown", Settings())
    assert unknown_result.decision is Decision.REQUIRE_APPROVAL
    assert unknown_result.security_tier is SecurityTier.T4


def test_unregistered_tool_has_no_invented_tier() -> None:
    registry = ToolRegistry((_definition("planner_known"),))
    result = MetadataPolicyEngine(registry).evaluate("planner_missing", Settings())
    assert result.decision is Decision.DENY
    assert result.reason == "TOOL_NOT_REGISTERED"
    assert result.security_tier is None
