"""Planner + Outlook DAG composition plan for XAPP-025."""

from __future__ import annotations

from dataclasses import dataclass

from m365_mcp.application_registry import ApplicationKey
from m365_mcp.xapp_dag_contract import DagOperationNode, DagRequest
from m365_mcp.xapp_dag_scheduler import DagSchedule, DagScheduleNode, schedule_dag


@dataclass(frozen=True)
class M365DagPlan:
    request: DagRequest
    schedule: DagSchedule
    planner_node_count: int
    outlook_node_count: int
    execution_performed: bool = False

    def __post_init__(self) -> None:
        if self.execution_performed or self.schedule.execution_performed:
            raise ValueError("M365 DAG plan must not execute nodes")
        if self.planner_node_count < 1 or self.outlook_node_count < 1:
            raise ValueError("M365 DAG requires Planner and Outlook nodes")
        if self.planner_node_count + self.outlook_node_count != len(self.request.nodes):
            raise ValueError("M365 DAG application counts are inconsistent")


def build_m365_dag_plan(
    dag_key: str,
    nodes: tuple[DagOperationNode, ...],
    *,
    max_parallel: int = 6,
) -> M365DagPlan:
    """Validate and topologically schedule a mixed-app DAG without execution."""
    planner_count = sum(node.application is ApplicationKey.PLANNER for node in nodes)
    outlook_count = sum(node.application is ApplicationKey.OUTLOOK for node in nodes)
    if planner_count < 1 or outlook_count < 1:
        raise ValueError("XAPP-025 requires at least one Planner and one Outlook node")
    if any(
        node.application is ApplicationKey.OUTLOOK and node.mutation
        for node in nodes
    ):
        raise ValueError("Outlook DAG nodes must remain non-mutating while RESERVED")

    request = DagRequest(dag_key=dag_key, nodes=nodes)
    schedule = schedule_dag(
        tuple(
            DagScheduleNode(node.node_id, node.depends_on)
            for node in request.nodes
        ),
        max_parallel=max_parallel,
    )
    return M365DagPlan(
        request=request,
        schedule=schedule,
        planner_node_count=planner_count,
        outlook_node_count=outlook_count,
    )


__all__ = ["M365DagPlan", "build_m365_dag_plan"]
