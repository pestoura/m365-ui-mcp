"""Cycle validation and deterministic bounded topological scheduling for XAPP-006."""

from __future__ import annotations

from dataclasses import dataclass

_MAX_DAG_NODES = 100
_MAX_PARALLEL = 6


def _token(field: str, value: str) -> None:
    if not value or value != value.strip() or any(char.isspace() for char in value):
        raise ValueError(f"{field} must be a non-empty semantic token")


@dataclass(frozen=True)
class DagScheduleNode:
    node_id: str
    depends_on: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _token("node_id", self.node_id)
        if self.node_id in self.depends_on:
            raise ValueError("DAG node cannot depend on itself")
        if len(self.depends_on) != len(set(self.depends_on)):
            raise ValueError("DAG dependencies must be unique")
        for dependency in self.depends_on:
            _token("dependency", dependency)


@dataclass(frozen=True)
class DagSchedule:
    waves: tuple[tuple[str, ...], ...]
    max_parallel: int
    acyclic: bool = True
    execution_performed: bool = False

    def __post_init__(self) -> None:
        if not 1 <= self.max_parallel <= _MAX_PARALLEL:
            raise ValueError("max_parallel must be between 1 and 6")
        if not self.acyclic:
            raise ValueError("DAG schedule must be acyclic")
        if self.execution_performed:
            raise ValueError("DAG scheduler must not execute nodes")
        flat = tuple(node_id for wave in self.waves for node_id in wave)
        if len(flat) != len(set(flat)):
            raise ValueError("DAG schedule node ids must be unique")
        if any(not wave or len(wave) > self.max_parallel for wave in self.waves):
            raise ValueError("DAG schedule waves must be non-empty and bounded")


def schedule_dag(
    nodes: tuple[DagScheduleNode, ...],
    *,
    max_parallel: int = _MAX_PARALLEL,
) -> DagSchedule:
    """Validate acyclicity and produce deterministic topological execution waves."""
    if not nodes:
        raise ValueError("DAG scheduler requires at least one node")
    if len(nodes) > _MAX_DAG_NODES:
        raise ValueError("DAG scheduler exceeds bounded node count")
    if not 1 <= max_parallel <= _MAX_PARALLEL:
        raise ValueError("max_parallel must be between 1 and 6")
    ids = tuple(node.node_id for node in nodes)
    if len(ids) != len(set(ids)):
        raise ValueError("DAG scheduler node ids must be unique")
    known = set(ids)
    for node in nodes:
        if set(node.depends_on) - known:
            raise ValueError("DAG dependency references unknown node")

    dependencies = {node.node_id: set(node.depends_on) for node in nodes}
    remaining = set(ids)
    waves: list[tuple[str, ...]] = []
    while remaining:
        ready = tuple(
            sorted(
                node_id
                for node_id in remaining
                if not (dependencies[node_id] & remaining)
            )
        )
        if not ready:
            raise ValueError("DAG contains a dependency cycle")
        selected = ready[:max_parallel]
        waves.append(selected)
        remaining.difference_update(selected)
    return DagSchedule(waves=tuple(waves), max_parallel=max_parallel)


__all__ = ["DagSchedule", "DagScheduleNode", "schedule_dag"]
