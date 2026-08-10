from __future__ import annotations

import pytest

from m365_mcp.xapp_dag_scheduler import DagScheduleNode, schedule_dag


def test_dag_scheduler_builds_dependency_safe_bounded_waves() -> None:
    schedule = schedule_dag(
        (
            DagScheduleNode("publish", depends_on=("transform",)),
            DagScheduleNode("fetch-a"),
            DagScheduleNode("transform", depends_on=("fetch-a", "fetch-b")),
            DagScheduleNode("fetch-b"),
            DagScheduleNode("independent"),
        ),
        max_parallel=2,
    )
    assert schedule.waves == (
        ("fetch-a", "fetch-b"),
        ("independent", "transform"),
        ("publish",),
    )
    assert schedule.execution_performed is False
    assert schedule.acyclic is True


def test_dag_scheduler_detects_cycles_and_invalid_parallelism() -> None:
    with pytest.raises(ValueError, match="dependency cycle"):
        schedule_dag(
            (
                DagScheduleNode("node-a", depends_on=("node-b",)),
                DagScheduleNode("node-b", depends_on=("node-a",)),
            )
        )
    with pytest.raises(ValueError, match="between 1 and 6"):
        schedule_dag((DagScheduleNode("node-a"),), max_parallel=7)
