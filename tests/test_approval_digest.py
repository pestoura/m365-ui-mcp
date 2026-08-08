from __future__ import annotations

import pytest

from m365_mcp.approval_digest import build_approval_plan_digest
from m365_mcp.plan_policy import PlanKind, PolicyNode, PolicyPlan
from m365_mcp.policy import MetadataPolicyEngine
from m365_mcp.policy_scope import canonical_policy_scope
from m365_mcp.tool_registry import (
    CompatibilityRequirement,
    ImplementationState,
    MutationClass,
    ToolDefinition,
    ToolRegistry,
    default_tool_registry,
)


def _update_definition(*, version: str = "test-v1") -> ToolDefinition:
    return ToolDefinition(
        name="m365_test_update",
        version=version,
        application="core",
        surface="test",
        domain="test",
        input_schema={"type": "object", "properties": {}, "additionalProperties": False},
        output_schema={"type": "object", "properties": {}},
        mutation_class=MutationClass.UPDATE,
        risk_class="READ_ONLY",
        implementation_state=ImplementationState.SPECIFIED_ONLY,
        capability_keys=(),
        ui_contract_dependencies=(),
        read_back_strategy="TEST_READ_BACK",
        idempotency_semantics="key_required",
        approval_requirement="required",
        compatibility_requirement=CompatibilityRequirement.INTERNAL_ONLY,
    )


def _engine(*, version: str = "test-v1") -> MetadataPolicyEngine:
    read = default_tool_registry().get("planner_plan_list")
    return MetadataPolicyEngine(ToolRegistry((read, _update_definition(version=version))))


def _mutating_plan() -> PolicyPlan:
    return PolicyPlan(
        PlanKind.RUNBOOK,
        (
            PolicyNode("read", "planner_plan_list"),
            PolicyNode("update", "m365_test_update", depends_on=("read",)),
        ),
    )


def test_same_exact_plan_produces_same_canonical_digest() -> None:
    first = build_approval_plan_digest(_mutating_plan(), engine=_engine())
    second = build_approval_plan_digest(_mutating_plan(), engine=_engine())

    assert first == second
    assert first.schema_version == "approval-plan-v1"
    assert first.algorithm == "sha256"
    assert len(first.value) == 64
    assert first.node_count == 2


def test_node_order_is_bound_into_approval_digest() -> None:
    original = _mutating_plan()
    reordered = PolicyPlan(
        PlanKind.RUNBOOK,
        (
            PolicyNode("update", "m365_test_update"),
            PolicyNode("read", "planner_plan_list"),
        ),
    )

    assert build_approval_plan_digest(original, engine=_engine()).value != (
        build_approval_plan_digest(reordered, engine=_engine()).value
    )


def test_tool_version_is_bound_into_approval_digest() -> None:
    plan = _mutating_plan()

    assert build_approval_plan_digest(plan, engine=_engine(version="v1")).value != (
        build_approval_plan_digest(plan, engine=_engine(version="v2")).value
    )


def test_plan_kind_is_bound_into_approval_digest() -> None:
    nodes = _mutating_plan().nodes
    batch = PolicyPlan(PlanKind.BATCH, nodes)
    runbook = PolicyPlan(PlanKind.RUNBOOK, nodes)

    assert build_approval_plan_digest(batch, engine=_engine()).value != (
        build_approval_plan_digest(runbook, engine=_engine()).value
    )


def test_dependency_order_is_canonicalized() -> None:
    read = default_tool_registry().get("planner_plan_list")
    engine = MetadataPolicyEngine(ToolRegistry((read, _update_definition())))
    prefix = (
        PolicyNode("one", "planner_plan_list"),
        PolicyNode("two", "planner_plan_list"),
    )
    first = PolicyPlan(
        PlanKind.DAG,
        prefix + (PolicyNode("update", "m365_test_update", depends_on=("one", "two")),),
    )
    second = PolicyPlan(
        PlanKind.DAG,
        prefix + (PolicyNode("update", "m365_test_update", depends_on=("two", "one")),),
    )

    assert build_approval_plan_digest(first, engine=engine).value == (
        build_approval_plan_digest(second, engine=engine).value
    )


def test_read_only_and_single_node_plans_do_not_produce_approval_digest() -> None:
    read_only = PolicyPlan(
        PlanKind.BATCH,
        (
            PolicyNode("one", "planner_plan_list"),
            PolicyNode("two", "planner_plan_list"),
        ),
    )
    single = PolicyPlan(
        PlanKind.BATCH,
        (PolicyNode("update", "m365_test_update"),),
    )

    with pytest.raises(ValueError, match="at least one mutating node"):
        build_approval_plan_digest(read_only)
    with pytest.raises(ValueError, match="multi-node plan"):
        build_approval_plan_digest(single, engine=_engine())


def test_unregistered_tool_and_scope_mismatch_fail_closed() -> None:
    unknown = PolicyPlan(
        PlanKind.BATCH,
        (
            PolicyNode("read", "planner_plan_list"),
            PolicyNode("unknown", "m365_unknown", mutation=True),
        ),
    )
    planner_registry = default_tool_registry()
    account_scope = canonical_policy_scope(planner_registry.get("planner_plan_list"))
    scope_mismatch = PolicyPlan(
        PlanKind.BATCH,
        (
            PolicyNode("read", "planner_plan_list"),
            PolicyNode(
                "task",
                "planner_task_list",
                scope=account_scope,
                mutation=True,
            ),
        ),
    )

    with pytest.raises(ValueError, match="unregistered tool"):
        build_approval_plan_digest(unknown)
    with pytest.raises(ValueError, match="invalid node scope"):
        build_approval_plan_digest(scope_mismatch)
