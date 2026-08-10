from __future__ import annotations

import pytest

from m365_mcp.plan_policy import NodePolicyResult, PlanKind, PlanPolicyResult
from m365_mcp.policy import Decision, PolicyResult
from m365_mcp.xapp_node_governance import (
    GovernedPlanDisposition,
    NodeEvidenceBinding,
    bind_node_governance,
)


def _policy_result() -> PlanPolicyResult:
    return PlanPolicyResult(
        kind=PlanKind.BATCH,
        decision=Decision.DENY,
        nodes=(
            NodePolicyResult(
                "read-node",
                "planner.list_tasks",
                PolicyResult(Decision.ALLOW, "REGISTERED_READ_TOOL"),
            ),
            NodePolicyResult(
                "write-node",
                "planner.update_task",
                PolicyResult(Decision.REQUIRE_APPROVAL, "MUTATION_REQUIRES_APPROVAL"),
            ),
            NodePolicyResult(
                "denied-node",
                "unknown.tool",
                PolicyResult(Decision.DENY, "TOOL_NOT_REGISTERED"),
            ),
        ),
    )


def test_each_node_requires_its_own_policy_approval_and_evidence_binding() -> None:
    result = bind_node_governance(
        _policy_result(),
        approval_node_ids=("write-node",),
        evidence_bindings=(
            NodeEvidenceBinding("read-node", "evidence-read"),
            NodeEvidenceBinding("write-node", "evidence-write"),
            NodeEvidenceBinding("denied-node", "evidence-denied"),
        ),
    )
    by_id = {node.node_id: node for node in result.nodes}
    assert by_id["read-node"].executable is True
    assert by_id["write-node"].approval_required is True
    assert by_id["write-node"].executable is True
    assert by_id["denied-node"].executable is False
    assert result.executable_node_ids == ("read-node", "write-node")


def test_missing_per_node_binding_fails_closed_and_no_aggregate_approval_exists() -> None:
    result = bind_node_governance(
        _policy_result(),
        evidence_bindings=(NodeEvidenceBinding("write-node", "evidence-write"),),
    )
    by_id = {node.node_id: node for node in result.nodes}
    assert by_id["read-node"].reason == "EVIDENCE_NOT_BOUND"
    assert by_id["write-node"].reason == "APPROVAL_NOT_BOUND"
    assert result.executable_node_ids == ()
    with pytest.raises(ValueError, match="aggregate plan approval"):
        GovernedPlanDisposition(nodes=(), aggregate_approval_available=True)
