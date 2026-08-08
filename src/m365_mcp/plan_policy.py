"""Per-node policy evaluation for composite execution plans.

CORE-034 makes every BATCH, DAG and RUNBOOK node independently subject to the
same metadata, tier and scope-aware policy used by DIRECT execution. This
module evaluates plans only; it does not schedule, execute or mutate anything.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from m365_mcp.config import Settings
from m365_mcp.policy import Decision, MetadataPolicyEngine, PolicyResult
from m365_mcp.policy_scope import PolicyScope


class PlanKind(StrEnum):
    """Closed composite plan kinds governed by per-node policy."""

    BATCH = "BATCH"
    DAG = "DAG"
    RUNBOOK = "RUNBOOK"


@dataclass(frozen=True)
class PolicyNode:
    """One semantic operation requiring an independent policy decision."""

    node_id: str
    tool: str
    scope: PolicyScope | None = None
    mutation: bool = False
    depends_on: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.node_id or self.node_id != self.node_id.strip():
            raise ValueError("plan policy node_id must be non-empty and trimmed")
        if not self.tool or self.tool != self.tool.strip():
            raise ValueError("plan policy tool must be non-empty and trimmed")
        if self.node_id in self.depends_on:
            raise ValueError("plan policy node cannot depend on itself")
        if len(set(self.depends_on)) != len(self.depends_on):
            raise ValueError("plan policy dependencies must be unique")


@dataclass(frozen=True)
class PolicyPlan:
    """Bounded composite policy input with no aggregate authorization flag."""

    kind: PlanKind
    nodes: tuple[PolicyNode, ...]

    def __post_init__(self) -> None:
        if not self.nodes:
            raise ValueError("plan policy requires at least one node")
        node_ids = tuple(node.node_id for node in self.nodes)
        if len(set(node_ids)) != len(node_ids):
            raise ValueError("plan policy node ids must be unique")
        known = set(node_ids)
        for node in self.nodes:
            unknown = set(node.depends_on) - known
            if unknown:
                raise ValueError("plan policy dependency references unknown node")


@dataclass(frozen=True)
class NodePolicyResult:
    """Policy result bound to exactly one plan node."""

    node_id: str
    tool: str
    result: PolicyResult


@dataclass(frozen=True)
class PlanPolicyResult:
    """Aggregate disposition derived only from completed per-node decisions."""

    kind: PlanKind
    decision: Decision
    nodes: tuple[NodePolicyResult, ...]

    @property
    def denied_node_ids(self) -> tuple[str, ...]:
        return tuple(
            node.node_id for node in self.nodes if node.result.decision is Decision.DENY
        )

    @property
    def approval_node_ids(self) -> tuple[str, ...]:
        return tuple(
            node.node_id
            for node in self.nodes
            if node.result.decision is Decision.REQUIRE_APPROVAL
        )


def _aggregate_decision(results: tuple[NodePolicyResult, ...]) -> Decision:
    if any(node.result.decision is Decision.DENY for node in results):
        return Decision.DENY
    if any(node.result.decision is Decision.REQUIRE_APPROVAL for node in results):
        return Decision.REQUIRE_APPROVAL
    return Decision.ALLOW


def evaluate_plan_policy(
    plan: PolicyPlan,
    settings: Settings,
    *,
    engine: MetadataPolicyEngine | None = None,
) -> PlanPolicyResult:
    """Evaluate every node independently; never authorize by plan membership."""
    policy_engine = engine or MetadataPolicyEngine()
    node_results = tuple(
        NodePolicyResult(
            node_id=node.node_id,
            tool=node.tool,
            result=policy_engine.evaluate(
                node.tool,
                settings,
                mutation=node.mutation,
                scope=node.scope,
            ),
        )
        for node in plan.nodes
    )
    return PlanPolicyResult(
        kind=plan.kind,
        decision=_aggregate_decision(node_results),
        nodes=node_results,
    )


__all__ = [
    "NodePolicyResult",
    "PlanKind",
    "PlanPolicyResult",
    "PolicyNode",
    "PolicyPlan",
    "evaluate_plan_policy",
]
