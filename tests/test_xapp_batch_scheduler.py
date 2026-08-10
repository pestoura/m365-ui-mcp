from __future__ import annotations

import pytest

from m365_mcp.xapp_batch_scheduler import BatchScheduleNode, schedule_bounded_batch


def test_batch_scheduler_builds_deterministic_bounded_waves_without_execution() -> None:
    nodes = tuple(BatchScheduleNode(f"node-{index}") for index in (5, 2, 1, 4, 3))
    schedule = schedule_bounded_batch(nodes, max_parallel=2)
    assert schedule.waves == (
        ("node-1", "node-2"),
        ("node-3", "node-4"),
        ("node-5",),
    )
    assert schedule.node_count == 5
    assert schedule.execution_performed is False


def test_batch_scheduler_enforces_parallel_and_unique_bounds() -> None:
    with pytest.raises(ValueError, match="between 1 and 6"):
        schedule_bounded_batch((BatchScheduleNode("node-a"),), max_parallel=7)
    with pytest.raises(ValueError, match="must be unique"):
        schedule_bounded_batch(
            (BatchScheduleNode("node-a"), BatchScheduleNode("node-a")),
        )
