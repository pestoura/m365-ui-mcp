"""Side-effect-free policy simulation for CORE-043.

Simulation reuses CORE-034 per-node policy evaluation and only projects bounded
policy metadata. It never invokes browser execution, approval consumption,
idempotency persistence, checkpoint persistence, or Microsoft 365 mutation.
"""

from __future__ import annotations

from dataclasses import dataclass

from m365_mcp.config import Settings
from m365_mcp.plan_policy import PolicyPlan, evaluate_plan_policy
from m365_mcp.policy import Decision, MetadataPolicyEngine
from m365_mcp.policy_scope import PolicyScope


@dataclass(frozen=True)
class SimulatedNodeOutcome:
    """Bounded dry-run outcome for exactly one composite-plan node."""

    node_id: str
    tool: str
    decision: Decision
    reason: str
    application: str | None
    mutation_class: str | None
    security_tier: str | None
    capability_keys: tuple[str, ...]
    scope: PolicyScope | None
    scope_reason: str | None
    scope_derived: bool
    depends_on: tuple[str, ...]
    mutation_requested: bool
    mutation_performed: bool = False


@dataclass(frozen=True)
class PolicySimulation:
    """Complete dry-run result; aggregate decision is informational only."""

    plan_kind: str
    aggregate_decision: Decision
    nodes: tuple[SimulatedNodeOutcome, ...]
    dry_run: bool = True
    side_effects_performed: bool = False

    @property
    def denied_node_ids(self) -> tuple[str, ...]:
        return tuple(node.node_id for node in self.nodes if node.decision is Decision.DENY)

    @property
    def approval_node_ids(self) -> tuple[str, ...]:
        return tuple(
            node.node_id
            for node in self.nodes
            if node.decision is Decision.REQUIRE_APPROVAL
        )


def simulate_policy_plan(
    plan: PolicyPlan,
    settings: Settings,
    *,
    engine: MetadataPolicyEngine | None = None,
) -> PolicySimulation:
    """Evaluate every node and project outcomes without performing any action."""
    evaluated = evaluate_plan_policy(plan, settings, engine=engine)
    by_id = {node.node_id: node for node in plan.nodes}
    outcomes = tuple(
        SimulatedNodeOutcome(
            node_id=node_result.node_id,
            tool=node_result.tool,
            decision=node_result.result.decision,
            reason=node_result.result.reason,
            application=node_result.result.application,
            mutation_class=(
                node_result.result.mutation_class.value
                if node_result.result.mutation_class is not None
                else None
            ),
            security_tier=(
                node_result.result.security_tier.name
                if node_result.result.security_tier is not None
                else None
            ),
            capability_keys=node_result.result.capability_keys,
            scope=node_result.result.scope,
            scope_reason=node_result.result.scope_reason,
            scope_derived=node_result.result.scope_derived,
            depends_on=by_id[node_result.node_id].depends_on,
            mutation_requested=by_id[node_result.node_id].mutation,
        )
        for node_result in evaluated.nodes
    )
    return PolicySimulation(
        plan_kind=evaluated.kind.value,
        aggregate_decision=evaluated.decision,
        nodes=outcomes,
    )


__all__ = ["PolicySimulation", "SimulatedNodeOutcome", "simulate_policy_plan"]
