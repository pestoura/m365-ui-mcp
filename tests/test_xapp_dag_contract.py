from __future__ import annotations

import pytest

from m365_mcp.application_registry import ApplicationKey
from m365_mcp.xapp_dag_contract import DagOperationNode, DagRequest


def test_dag_contract_validates_known_dependencies_without_scheduling() -> None:
    dag = DagRequest(
        dag_key="dag-001",
        nodes=(
            DagOperationNode("fetch", ApplicationKey.OUTLOOK, "outlook.synthetic"),
            DagOperationNode(
                "update",
                ApplicationKey.PLANNER,
                "planner.update_task",
                depends_on=("fetch",),
                mutation=True,
            ),
        ),
    )
    projection = dag.to_projection()
    assert projection["node_count"] == 2
    assert projection["node_ids"] == ("fetch", "update")
    assert projection["aggregate_authorization_available"] is False


def test_dag_contract_rejects_unknown_self_and_aggregate_authorization() -> None:
    with pytest.raises(ValueError, match="depend on itself"):
        DagOperationNode(
            "node-a",
            ApplicationKey.PLANNER,
            "planner.list_tasks",
            depends_on=("node-a",),
        )
    with pytest.raises(ValueError, match="unknown node"):
        DagRequest(
            dag_key="dag-unknown",
            nodes=(
                DagOperationNode(
                    "node-a",
                    ApplicationKey.PLANNER,
                    "planner.list_tasks",
                    depends_on=("missing",),
                ),
            ),
        )
    node = DagOperationNode("node-a", ApplicationKey.PLANNER, "planner.list_tasks")
    with pytest.raises(ValueError, match="aggregate authorization"):
        DagRequest(
            dag_key="dag-unsafe",
            nodes=(node,),
            aggregate_authorization_available=True,
        )
