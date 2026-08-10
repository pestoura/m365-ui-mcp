"""Cancellation and deadline propagation planning for XAPP-008.

The module computes deterministic node dispositions only. It does not cancel a
running operation, sleep, inspect a clock, or execute downstream work.
"""

from __future__ import annotations

from dataclasses import dataclass

_MAX_NODES = 100


def _token(field: str, value: str) -> None:
    if not value or value != value.strip() or any(char.isspace() for char in value):
        raise ValueError(f"{field} must be a non-empty semantic token")


@dataclass(frozen=True)
class PropagationNode:
    node_id: str
    depends_on: tuple[str, ...] = ()
    deadline_seconds_from_start: int | None = None

    def __post_init__(self) -> None:
        _token("node_id", self.node_id)
        if self.node_id in self.depends_on:
            raise ValueError("propagation node cannot depend on itself")
        if len(self.depends_on) != len(set(self.depends_on)):
            raise ValueError("propagation dependencies must be unique")
        for dependency in self.depends_on:
            _token("dependency", dependency)
        if self.deadline_seconds_from_start is not None:
            if self.deadline_seconds_from_start <= 0:
                raise ValueError("deadline must be a positive relative duration")


@dataclass(frozen=True)
class NodePropagationDisposition:
    node_id: str
    cancellation_requested: bool
    effective_deadline_seconds_from_start: int | None


@dataclass(frozen=True)
class CancellationDeadlinePlan:
    nodes: tuple[NodePropagationDisposition, ...]
    execution_performed: bool = False

    def __post_init__(self) -> None:
        ids = tuple(node.node_id for node in self.nodes)
        if len(ids) != len(set(ids)):
            raise ValueError("propagation dispositions must have unique node ids")
        if self.execution_performed:
            raise ValueError("propagation planner must not execute nodes")


def plan_cancellation_deadline_propagation(
    nodes: tuple[PropagationNode, ...],
    *,
    cancellation_node_ids: tuple[str, ...] = (),
    root_deadline_seconds_from_start: int | None = None,
) -> CancellationDeadlinePlan:
    """Propagate cancellation downstream and the tightest deadline downstream."""
    if not nodes:
        raise ValueError("propagation planner requires at least one node")
    if len(nodes) > _MAX_NODES:
        raise ValueError("propagation planner exceeds bounded node count")
    if root_deadline_seconds_from_start is not None:
        if root_deadline_seconds_from_start <= 0:
            raise ValueError("root deadline must be a positive relative duration")
    ids = tuple(node.node_id for node in nodes)
    if len(ids) != len(set(ids)):
        raise ValueError("propagation node ids must be unique")
    known = set(ids)
    for node in nodes:
        if set(node.depends_on) - known:
            raise ValueError("propagation dependency references unknown node")
    if len(cancellation_node_ids) != len(set(cancellation_node_ids)):
        raise ValueError("cancellation node ids must be unique")
    if set(cancellation_node_ids) - known:
        raise ValueError("cancellation references unknown node")

    cancelled = set(cancellation_node_ids)
    changed = True
    while changed:
        changed = False
        for node in nodes:
            if node.node_id not in cancelled and set(node.depends_on) & cancelled:
                cancelled.add(node.node_id)
                changed = True

    deadlines: dict[str, int | None] = {}
    remaining = set(ids)
    by_id = {node.node_id: node for node in nodes}
    while remaining:
        ready = tuple(
            node_id
            for node_id in sorted(remaining)
            if not (set(by_id[node_id].depends_on) & remaining)
        )
        if not ready:
            raise ValueError("propagation graph contains a dependency cycle")
        for node_id in ready:
            node = by_id[node_id]
            candidates = [
                deadline
                for deadline in (
                    root_deadline_seconds_from_start,
                    node.deadline_seconds_from_start,
                    *(deadlines[dep] for dep in node.depends_on),
                )
                if deadline is not None
            ]
            deadlines[node_id] = min(candidates) if candidates else None
            remaining.remove(node_id)

    dispositions = tuple(
        NodePropagationDisposition(
            node_id=node_id,
            cancellation_requested=node_id in cancelled,
            effective_deadline_seconds_from_start=deadlines[node_id],
        )
        for node_id in sorted(ids)
    )
    return CancellationDeadlinePlan(nodes=dispositions)


__all__ = [
    "CancellationDeadlinePlan",
    "NodePropagationDisposition",
    "PropagationNode",
    "plan_cancellation_deadline_propagation",
]
