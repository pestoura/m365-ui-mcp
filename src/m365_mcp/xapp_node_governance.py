"""Per-node policy, approval and evidence binding for XAPP-004."""

from __future__ import annotations

from dataclasses import dataclass

from m365_mcp.plan_policy import PlanPolicyResult
from m365_mcp.policy import Decision

_MAX_BINDINGS = 100


def _token(field: str, value: str) -> None:
    if not value or value != value.strip() or any(char.isspace() for char in value):
        raise ValueError(f"{field} must be a non-empty semantic token")
    if "://" in value:
        raise ValueError(f"{field} must not encode a URL")


@dataclass(frozen=True)
class NodeEvidenceBinding:
    node_id: str
    evidence_reference_id: str

    def __post_init__(self) -> None:
        _token("node_id", self.node_id)
        _token("evidence_reference_id", self.evidence_reference_id)


@dataclass(frozen=True)
class NodeGovernanceDisposition:
    node_id: str
    decision: Decision
    approval_required: bool
    approval_bound: bool
    evidence_bound: bool
    executable: bool
    reason: str


@dataclass(frozen=True)
class GovernedPlanDisposition:
    nodes: tuple[NodeGovernanceDisposition, ...]
    aggregate_approval_available: bool = False

    def __post_init__(self) -> None:
        if self.aggregate_approval_available:
            raise ValueError("aggregate plan approval is not available")
        ids = tuple(node.node_id for node in self.nodes)
        if len(ids) != len(set(ids)):
            raise ValueError("governance node ids must be unique")

    @property
    def executable_node_ids(self) -> tuple[str, ...]:
        return tuple(node.node_id for node in self.nodes if node.executable)


def bind_node_governance(
    policy_result: PlanPolicyResult,
    *,
    approval_node_ids: tuple[str, ...] = (),
    evidence_bindings: tuple[NodeEvidenceBinding, ...] = (),
) -> GovernedPlanDisposition:
    """Bind policy, approval and evidence independently for every plan node."""
    if len(policy_result.nodes) > _MAX_BINDINGS:
        raise ValueError("plan governance exceeds bounded node count")
    known = {node.node_id for node in policy_result.nodes}
    if len(approval_node_ids) != len(set(approval_node_ids)):
        raise ValueError("approval node ids must be unique")
    if set(approval_node_ids) - known:
        raise ValueError("approval references unknown plan node")
    evidence_by_node: dict[str, str] = {}
    for binding in evidence_bindings:
        if binding.node_id not in known:
            raise ValueError("evidence references unknown plan node")
        if binding.node_id in evidence_by_node:
            raise ValueError("each plan node accepts one evidence binding")
        evidence_by_node[binding.node_id] = binding.evidence_reference_id

    dispositions: list[NodeGovernanceDisposition] = []
    for node in policy_result.nodes:
        decision = node.result.decision
        approval_required = decision is Decision.REQUIRE_APPROVAL
        approval_bound = node.node_id in approval_node_ids
        evidence_bound = node.node_id in evidence_by_node
        executable = (
            decision is not Decision.DENY
            and (not approval_required or approval_bound)
            and evidence_bound
        )
        if decision is Decision.DENY:
            reason = node.result.reason
        elif approval_required and not approval_bound:
            reason = "APPROVAL_NOT_BOUND"
        elif not evidence_bound:
            reason = "EVIDENCE_NOT_BOUND"
        else:
            reason = "NODE_GOVERNANCE_SATISFIED"
        dispositions.append(
            NodeGovernanceDisposition(
                node_id=node.node_id,
                decision=decision,
                approval_required=approval_required,
                approval_bound=approval_bound,
                evidence_bound=evidence_bound,
                executable=executable,
                reason=reason,
            )
        )
    return GovernedPlanDisposition(nodes=tuple(dispositions))


__all__ = [
    "GovernedPlanDisposition",
    "NodeEvidenceBinding",
    "NodeGovernanceDisposition",
    "bind_node_governance",
]
