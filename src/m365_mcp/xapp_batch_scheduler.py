"""Deterministic bounded BATCH scheduling plan for XAPP-003."""

from __future__ import annotations

from dataclasses import dataclass

_MAX_BATCH_NODES = 50
_MAX_PARALLEL = 6


def _token(field: str, value: str) -> None:
    if not value or value != value.strip() or any(char.isspace() for char in value):
        raise ValueError(f"{field} must be a non-empty semantic token")


@dataclass(frozen=True)
class BatchScheduleNode:
    node_id: str

    def __post_init__(self) -> None:
        _token("node_id", self.node_id)


@dataclass(frozen=True)
class BoundedBatchSchedule:
    waves: tuple[tuple[str, ...], ...]
    max_parallel: int
    execution_performed: bool = False

    def __post_init__(self) -> None:
        if not 1 <= self.max_parallel <= _MAX_PARALLEL:
            raise ValueError("max_parallel must be between 1 and 6")
        flat = tuple(node_id for wave in self.waves for node_id in wave)
        if len(flat) != len(set(flat)):
            raise ValueError("scheduled node ids must be unique")
        if any(not wave or len(wave) > self.max_parallel for wave in self.waves):
            raise ValueError("each BATCH wave must be non-empty and bounded")
        if self.execution_performed:
            raise ValueError("BATCH scheduler must not execute nodes")

    @property
    def node_count(self) -> int:
        return sum(len(wave) for wave in self.waves)


def schedule_bounded_batch(
    nodes: tuple[BatchScheduleNode, ...],
    *,
    max_parallel: int = _MAX_PARALLEL,
) -> BoundedBatchSchedule:
    """Build deterministic execution waves; never execute the nodes."""
    if not nodes:
        raise ValueError("BATCH scheduler requires at least one node")
    if len(nodes) > _MAX_BATCH_NODES:
        raise ValueError("BATCH scheduler exceeds bounded node count")
    if not 1 <= max_parallel <= _MAX_PARALLEL:
        raise ValueError("max_parallel must be between 1 and 6")
    node_ids = tuple(node.node_id for node in nodes)
    if len(node_ids) != len(set(node_ids)):
        raise ValueError("BATCH scheduler node ids must be unique")
    ordered = tuple(sorted(node_ids))
    waves = tuple(
        ordered[index : index + max_parallel]
        for index in range(0, len(ordered), max_parallel)
    )
    return BoundedBatchSchedule(waves=waves, max_parallel=max_parallel)


__all__ = ["BatchScheduleNode", "BoundedBatchSchedule", "schedule_bounded_batch"]
