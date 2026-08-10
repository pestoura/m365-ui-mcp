from __future__ import annotations

import pytest

from m365_mcp.application_registry import ApplicationKey
from m365_mcp.xapp_batch_contract import BatchOperationRequest, BatchRequest


def test_batch_contract_is_bounded_unique_and_has_no_aggregate_authorization() -> None:
    batch = BatchRequest(
        batch_key="batch-001",
        nodes=(
            BatchOperationRequest("node-a", ApplicationKey.PLANNER, "planner.list_tasks"),
            BatchOperationRequest("node-b", ApplicationKey.OUTLOOK, "outlook.synthetic"),
        ),
    )
    projection = batch.to_projection()
    assert projection["node_count"] == 2
    assert projection["node_ids"] == ("node-a", "node-b")
    assert projection["aggregate_authorization_available"] is False


def test_batch_contract_rejects_duplicate_nodes_and_aggregate_authorization() -> None:
    node = BatchOperationRequest("node-a", ApplicationKey.PLANNER, "planner.list_tasks")
    with pytest.raises(ValueError, match="node ids must be unique"):
        BatchRequest(batch_key="batch-duplicate", nodes=(node, node))
    with pytest.raises(ValueError, match="aggregate authorization"):
        BatchRequest(
            batch_key="batch-unsafe",
            nodes=(node,),
            aggregate_authorization_available=True,
        )
