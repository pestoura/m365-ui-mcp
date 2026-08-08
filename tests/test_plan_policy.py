from __future__ import annotations

from types import SimpleNamespace
from typing import cast

import pytest

from m365_mcp.config import Settings
from m365_mcp.plan_policy import PlanKind, PolicyNode, PolicyPlan, evaluate_plan_policy
from m365_mcp.policy import Decision, MetadataPolicyEngine
from m365_mcp.policy_scope import canonical_policy_scope
from m365_mcp.tool_registry import (
    CompatibilityRequirement,
    ImplementationState,
    MutationClass,
    ToolDefinition,
    ToolRegistry,
    default_tool_registry,
)


def _mutation_definition() -> ToolDefinition:
    return ToolDefinition(
        name="m365_test_update",
        version="test",
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


def test_batch_evaluates_every_node_independently() -> None:
    plan = PolicyPlan(
        PlanKind.BATCH,
        (
            PolicyNode("plans", "planner_plan_list"),
            PolicyNode("tasks", "planner_task_list"),
        ),
    )
    result = evaluate_plan_policy(plan, Settings())

    assert result.decision is Decision.ALLOW
    assert tuple(node.node_id for node in result.nodes) == ("plans", "tasks")
    assert all(node.result.decision is Decision.ALLOW for node in result.nodes)
    assert all(node.result.scope is not None for node in result.nodes)


def test_one_unknown_node_denies_plan_without_hiding_other_node_results() -> None:
    plan = PolicyPlan(
        PlanKind.RUNBOOK,
        (
            PolicyNode("known", "planner_plan_list"),
            PolicyNode("unknown", "planner_not_registered"),
            PolicyNode("known-again", "planner_task_list"),
        ),
    )
    result = evaluate_plan_policy(plan, Settings())

    assert result.decision is Decision.DENY
    assert result.denied_node_ids == ("unknown",)
    assert len(result.nodes) == 3
    assert result.nodes[0].result.decision is Decision.ALLOW
    assert result.nodes[2].result.decision is Decision.ALLOW


def test_scope_mismatch_denies_only_affected_node_and_denies_plan() -> None:
    registry = default_tool_registry()
    plan_scope = canonical_policy_scope(registry.get("planner_plan_list"))
    task_scope = canonical_policy_scope(registry.get("planner_task_list"))
    plan = PolicyPlan(
        PlanKind.DAG,
        (
            PolicyNode("plans", "planner_plan_list", scope=plan_scope),
            PolicyNode("tasks", "planner_task_list", scope=plan_scope, depends_on=("plans",)),
            PolicyNode("tasks-ok", "planner_task_list", scope=task_scope, depends_on=("plans",)),
        ),
    )
    result = evaluate_plan_policy(plan, Settings())

    assert result.decision is Decision.DENY
    assert result.denied_node_ids == ("tasks",)
    assert result.nodes[1].result.reason == "SCOPE_CONTAINER_MISMATCH"
    assert result.nodes[2].result.decision is Decision.ALLOW


def test_approval_requirement_is_preserved_per_node() -> None:
    planner = default_tool_registry().get("planner_plan_list")
    registry = ToolRegistry((planner, _mutation_definition()))
    engine = MetadataPolicyEngine(registry)
    permissive = cast(Settings, SimpleNamespace(allow_mutations=True))
    plan = PolicyPlan(
        PlanKind.BATCH,
        (
            PolicyNode("read", "planner_plan_list"),
            PolicyNode("update", "m365_test_update"),
        ),
    )
    result = evaluate_plan_policy(plan, permissive, engine=engine)

    assert result.decision is Decision.REQUIRE_APPROVAL
    assert result.approval_node_ids == ("update",)
    assert result.nodes[0].result.decision is Decision.ALLOW
    assert result.nodes[1].result.decision is Decision.REQUIRE_APPROVAL


def test_plan_membership_cannot_override_global_mutation_disablement() -> None:
    registry = ToolRegistry((_mutation_definition(),))
    engine = MetadataPolicyEngine(registry)
    plan = PolicyPlan(
        PlanKind.RUNBOOK,
        (PolicyNode("update", "m365_test_update"),),
    )
    result = evaluate_plan_policy(plan, Settings(), engine=engine)

    assert result.decision is Decision.DENY
    assert result.denied_node_ids == ("update",)
    assert result.nodes[0].result.reason == "MUTATIONS_DISABLED_IN_0_1_0"


def test_plan_rejects_duplicate_ids_self_dependencies_and_unknown_dependencies() -> None:
    with pytest.raises(ValueError, match="node ids must be unique"):
        PolicyPlan(
            PlanKind.BATCH,
            (
                PolicyNode("same", "planner_plan_list"),
                PolicyNode("same", "planner_task_list"),
            ),
        )

    with pytest.raises(ValueError, match="cannot depend on itself"):
        PolicyNode("self", "planner_plan_list", depends_on=("self",))

    with pytest.raises(ValueError, match="dependency references unknown node"):
        PolicyPlan(
            PlanKind.DAG,
            (PolicyNode("node", "planner_plan_list", depends_on=("missing",)),),
        )
