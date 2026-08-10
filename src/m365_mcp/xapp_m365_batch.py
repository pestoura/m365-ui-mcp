"""Planner + Outlook BATCH composition plan for XAPP-024.

This layer composes existing BATCH contracts and produces a deterministic
schedule only. Outlook nodes are restricted to non-mutating internal semantic
operations while Outlook remains RESERVED.
"""

from __future__ import annotations

from dataclasses import dataclass

from m365_mcp.application_registry import ApplicationKey
from m365_mcp.xapp_batch_contract import BatchOperationRequest, BatchRequest
from m365_mcp.xapp_batch_scheduler import (
    BatchScheduleNode,
    BoundedBatchSchedule,
    schedule_bounded_batch,
)


@dataclass(frozen=True)
class M365BatchPlan:
    request: BatchRequest
    schedule: BoundedBatchSchedule
    planner_node_count: int
    outlook_node_count: int
    execution_performed: bool = False

    def __post_init__(self) -> None:
        if self.execution_performed or self.schedule.execution_performed:
            raise ValueError("M365 BATCH plan must not execute nodes")
        if self.planner_node_count < 1 or self.outlook_node_count < 1:
            raise ValueError("M365 BATCH requires Planner and Outlook nodes")
        if self.planner_node_count + self.outlook_node_count != len(self.request.nodes):
            raise ValueError("M365 BATCH application counts are inconsistent")


def build_m365_batch_plan(
    batch_key: str,
    nodes: tuple[BatchOperationRequest, ...],
    *,
    max_parallel: int = 6,
) -> M365BatchPlan:
    """Build a mixed-app BATCH request and schedule without executing it."""
    planner_count = sum(node.application is ApplicationKey.PLANNER for node in nodes)
    outlook_count = sum(node.application is ApplicationKey.OUTLOOK for node in nodes)
    if planner_count < 1 or outlook_count < 1:
        raise ValueError("XAPP-024 requires at least one Planner and one Outlook node")
    if any(
        node.application is ApplicationKey.OUTLOOK and node.mutation
        for node in nodes
    ):
        raise ValueError("Outlook BATCH nodes must remain non-mutating while RESERVED")

    request = BatchRequest(batch_key=batch_key, nodes=nodes)
    schedule = schedule_bounded_batch(
        tuple(BatchScheduleNode(node.node_id) for node in request.nodes),
        max_parallel=max_parallel,
    )
    return M365BatchPlan(
        request=request,
        schedule=schedule,
        planner_node_count=planner_count,
        outlook_node_count=outlook_count,
    )


__all__ = ["M365BatchPlan", "build_m365_batch_plan"]
