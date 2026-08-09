from __future__ import annotations

from m365_mcp.apps.outlook import mock_ui, readiness, todo_task_reads
from m365_mcp.capability_registry import default_capability_registry
from m365_mcp.tool_registry import default_tool_registry


def _ready() -> readiness.OutlookReadinessReport:
    return readiness.OutlookReadinessReport(state=readiness.OutlookReadinessState.DISCOVERY_READY, primary_context_verified=True, shared_context_verified=False, candidate_count=1, observed_count=1, blocked_count=0, reattestation_count=0)


def test_todo_reads_and_list_filter() -> None:
    fixture = mock_ui.default_outlook_fixture()
    data = todo_task_reads.read_fixture_todo(fixture, readiness=_ready())
    assert len(data["lists"]) == 2  # type: ignore[arg-type]
    tasks = todo_task_reads.list_fixture_tasks(fixture, "todo-default", readiness=_ready())
    assert [item.task_key for item in tasks] == ["task-alpha", "task-charlie"]


def test_dangling_task_and_bad_due_offset_fail_closed() -> None:
    fixture = mock_ui.default_outlook_fixture()
    lists = (todo_task_reads.SyntheticTodoList("todo-a", "A"),)
    tasks = (todo_task_reads.SyntheticTodoTask("task-a", "missing", "A"),)
    try:
        todo_task_reads.read_fixture_todo(fixture, readiness=_ready(), lists=lists, tasks=tasks)
    except ValueError as exc:
        assert "reference" in str(exc)
    else:
        raise AssertionError("dangling task accepted")
    try:
        todo_task_reads.SyntheticTodoTask("task-b", "todo-a", "B", due_day_offset=4000)
    except ValueError as exc:
        assert "bounded" in str(exc)
    else:
        raise AssertionError("unbounded due date accepted")


def test_task_projection_excludes_identity_and_browser_primitives() -> None:
    fixture = mock_ui.default_outlook_fixture()
    projection = repr(todo_task_reads.list_fixture_tasks(fixture, "todo-default", readiness=_ready())[0].to_projection()).lower()
    for forbidden in ("@", "http", "://", "selector", "xpath", "javascript", "cookie", "tenant", "utc"):
        assert forbidden not in projection


def test_out028_keeps_outlook_activation_absent() -> None:
    assert default_tool_registry().by_application("outlook") == ()
    assert default_capability_registry().by_application("outlook") == ()
