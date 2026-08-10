from __future__ import annotations

import pytest

from m365_mcp.xapp_cancellation_deadlines import (
    PropagationNode,
    plan_cancellation_deadline_propagation,
)


def test_cancellation_and_tightest_deadline_propagate_downstream_only() -> None:
    plan = plan_cancellation_deadline_propagation(
        (
            PropagationNode("a", deadline_seconds_from_start=90),
            PropagationNode("b", depends_on=("a",), deadline_seconds_from_start=120),
            PropagationNode("c", depends_on=("b",)),
            PropagationNode("independent"),
        ),
        cancellation_node_ids=("a",),
        root_deadline_seconds_from_start=100,
    )
    by_id = {node.node_id: node for node in plan.nodes}
    assert by_id["a"].cancellation_requested is True
    assert by_id["b"].cancellation_requested is True
    assert by_id["c"].cancellation_requested is True
    assert by_id["independent"].cancellation_requested is False
    assert by_id["a"].effective_deadline_seconds_from_start == 90
    assert by_id["b"].effective_deadline_seconds_from_start == 90
    assert by_id["c"].effective_deadline_seconds_from_start == 90
    assert by_id["independent"].effective_deadline_seconds_from_start == 100
    assert plan.execution_performed is False


def test_propagation_rejects_cycle_and_unknown_cancellation() -> None:
    with pytest.raises(ValueError, match="dependency cycle"):
        plan_cancellation_deadline_propagation(
            (
                PropagationNode("a", depends_on=("b",)),
                PropagationNode("b", depends_on=("a",)),
            )
        )
    with pytest.raises(ValueError, match="unknown node"):
        plan_cancellation_deadline_propagation(
            (PropagationNode("a"),),
            cancellation_node_ids=("missing",),
        )
