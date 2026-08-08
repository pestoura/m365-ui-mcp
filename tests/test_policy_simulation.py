from __future__ import annotations

import inspect

import m365_mcp.plan_policy as plan_policy
import m365_mcp.policy as policy
import m365_mcp.policy_scope as policy_scope
import m365_mcp.policy_simulation as policy_simulation
from m365_mcp.config import Settings


def test_simulation_reports_every_node_without_performing_side_effects() -> None:
    plan = plan_policy.PolicyPlan(
        kind=plan_policy.PlanKind.DAG,
        nodes=(
            plan_policy.PolicyNode(node_id="health", tool="planner_health"),
            plan_policy.PolicyNode(
                node_id="plans",
                tool="planner_plan_list",
                depends_on=("health",),
            ),
        ),
    )

    result = policy_simulation.simulate_policy_plan(plan, Settings())

    assert result.dry_run is True
    assert result.side_effects_performed is False
    assert result.aggregate_decision is policy.Decision.ALLOW
    assert tuple(node.node_id for node in result.nodes) == ("health", "plans")
    assert all(node.decision is policy.Decision.ALLOW for node in result.nodes)
    assert all(node.mutation_performed is False for node in result.nodes)
    assert result.nodes[1].depends_on == ("health",)


def test_simulation_preserves_security_tier_scope_and_capability_context() -> None:
    plan = plan_policy.PolicyPlan(
        kind=plan_policy.PlanKind.RUNBOOK,
        nodes=(plan_policy.PolicyNode(node_id="plans", tool="planner_plan_list"),),
    )

    result = policy_simulation.simulate_policy_plan(plan, Settings())
    node = result.nodes[0]

    assert node.application == "planner"
    assert node.mutation_class == "READ"
    assert node.security_tier == "T2"
    assert node.capability_keys == ("plans.read",)
    assert node.scope is not None
    assert node.scope.application == "planner"
    assert node.scope_derived is True
    assert node.mutation_requested is False


def test_mutation_override_is_simulated_but_never_executed() -> None:
    plan = plan_policy.PolicyPlan(
        kind=plan_policy.PlanKind.BATCH,
        nodes=(
            plan_policy.PolicyNode(
                node_id="would_mutate",
                tool="planner_plan_list",
                mutation=True,
            ),
        ),
    )

    result = policy_simulation.simulate_policy_plan(plan, Settings())
    node = result.nodes[0]

    assert node.mutation_requested is True
    assert node.mutation_performed is False
    assert node.decision is policy.Decision.DENY
    assert node.reason == "MUTATIONS_DISABLED_IN_0_1_0"
    assert result.aggregate_decision is policy.Decision.DENY


def test_unknown_tool_and_scope_mismatch_fail_closed_per_node() -> None:
    wrong_scope = policy_scope.PolicyScope(
        application="outlook",
        surface="outlook_web",
        account_scope=policy_scope.AccountScope.PROFESSIONAL_SESSION,
        container_scope="mailbox",
        mailbox_scope=policy_scope.MailboxScope.PRIMARY,
        resource_scope=policy_scope.ResourceScope.CONTAINER,
    )
    plan = plan_policy.PolicyPlan(
        kind=plan_policy.PlanKind.BATCH,
        nodes=(
            plan_policy.PolicyNode(node_id="unknown", tool="not_registered"),
            plan_policy.PolicyNode(
                node_id="wrong_scope",
                tool="planner_plan_list",
                scope=wrong_scope,
            ),
        ),
    )

    result = policy_simulation.simulate_policy_plan(plan, Settings())

    assert result.aggregate_decision is policy.Decision.DENY
    assert result.denied_node_ids == ("unknown", "wrong_scope")
    assert result.nodes[0].reason == "TOOL_NOT_REGISTERED"
    assert result.nodes[1].decision is policy.Decision.DENY


def test_aggregate_decision_never_erases_per_node_outcomes() -> None:
    plan = plan_policy.PolicyPlan(
        kind=plan_policy.PlanKind.DAG,
        nodes=(
            plan_policy.PolicyNode(node_id="ok", tool="planner_health"),
            plan_policy.PolicyNode(node_id="blocked", tool="not_registered"),
        ),
    )

    result = policy_simulation.simulate_policy_plan(plan, Settings())

    assert result.aggregate_decision is policy.Decision.DENY
    assert result.nodes[0].decision is policy.Decision.ALLOW
    assert result.nodes[1].decision is policy.Decision.DENY
    assert result.denied_node_ids == ("blocked",)


def test_simulation_module_has_no_execution_or_persistence_dependencies() -> None:
    source = inspect.getsource(policy_simulation)
    forbidden = (
        "browser_worker",
        "ApprovalStore",
        "approval_store",
        "reserve_operation",
        "associate_result",
        "start_checkpoint",
        "transition_checkpoint",
        "sqlite3",
        "playwright",
    )

    assert all(token not in source for token in forbidden)


def test_all_current_planner_public_tools_are_simulatable() -> None:
    engine = policy.MetadataPolicyEngine()
    nodes = tuple(
        plan_policy.PolicyNode(node_id=f"node_{index}", tool=definition.name)
        for index, definition in enumerate(engine.registry.by_application("planner"), start=1)
    )
    plan = plan_policy.PolicyPlan(kind=plan_policy.PlanKind.BATCH, nodes=nodes)

    result = policy_simulation.simulate_policy_plan(plan, Settings(), engine=engine)

    assert len(result.nodes) == 17
    assert all(node.decision is policy.Decision.ALLOW for node in result.nodes)
    assert all(node.mutation_performed is False for node in result.nodes)
