from __future__ import annotations

import pytest

from m365_mcp.application_registry import (
    ApplicationKey,
    ApplicationState,
    default_application_registry,
)
from m365_mcp.apps.outlook import mock_ui, readiness, todo_task_mutations
from m365_mcp.apps.outlook import todo_task_reads
from m365_mcp.tool_registry import default_tool_registry


def _ready() -> readiness.OutlookReadinessReport:
    return readiness.OutlookReadinessReport(
        state=readiness.OutlookReadinessState.DISCOVERY_READY,
        primary_context_verified=True,
        shared_context_verified=False,
        candidate_count=1,
        observed_count=1,
        blocked_count=0,
        reattestation_count=0,
    )


def test_task_create_update_complete_delete_have_exact_read_back() -> None:
    fixture = mock_ui.default_outlook_fixture()
    lists, tasks = todo_task_reads.default_synthetic_todo()
    tasks, created = todo_task_mutations.apply_todo_task_mutation(
        fixture,
        lists,
        tasks,
        todo_task_mutations.TodoTaskMutationRequest(
            todo_task_mutations.TodoTaskAction.CREATE,
            "task-delta",
            "todo-default",
            "Synthetic delta",
        ),
        readiness=_ready(),
    )
    assert created.read_back is not None
    tasks, updated = todo_task_mutations.apply_todo_task_mutation(
        fixture,
        lists,
        tasks,
        todo_task_mutations.TodoTaskMutationRequest(
            todo_task_mutations.TodoTaskAction.UPDATE,
            "task-delta",
            "todo-project",
            "Synthetic delta revised",
        ),
        readiness=_ready(),
    )
    assert updated.read_back is not None
    assert updated.read_back.list_key == "todo-project"
    tasks, completed = todo_task_mutations.apply_todo_task_mutation(
        fixture,
        lists,
        tasks,
        todo_task_mutations.TodoTaskMutationRequest(
            todo_task_mutations.TodoTaskAction.COMPLETE,
            "task-delta",
        ),
        readiness=_ready(),
    )
    assert completed.read_back is not None
    assert completed.read_back.state is todo_task_reads.TaskState.COMPLETED
    tasks, deleted = todo_task_mutations.apply_todo_task_mutation(
        fixture,
        lists,
        tasks,
        todo_task_mutations.TodoTaskMutationRequest(
            todo_task_mutations.TodoTaskAction.DELETE,
            "task-delta",
        ),
        readiness=_ready(),
    )
    assert deleted.read_back is None
    assert all(item.task_key != "task-delta" for item in tasks)


def test_task_create_and_delete_are_idempotent() -> None:
    fixture = mock_ui.default_outlook_fixture()
    lists, tasks = todo_task_reads.default_synthetic_todo()
    _, repeated = todo_task_mutations.apply_todo_task_mutation(
        fixture,
        lists,
        tasks,
        todo_task_mutations.TodoTaskMutationRequest(
            todo_task_mutations.TodoTaskAction.CREATE,
            "task-alpha",
            "todo-default",
            "Review synthetic item",
        ),
        readiness=_ready(),
    )
    assert repeated.changed is False
    _, absent = todo_task_mutations.apply_todo_task_mutation(
        fixture,
        lists,
        tasks,
        todo_task_mutations.TodoTaskMutationRequest(
            todo_task_mutations.TodoTaskAction.DELETE,
            "task-missing",
        ),
        readiness=_ready(),
    )
    assert absent.changed is False


def test_task_mutation_fails_closed_for_unknown_list_and_missing_update() -> None:
    fixture = mock_ui.default_outlook_fixture()
    lists, tasks = todo_task_reads.default_synthetic_todo()
    with pytest.raises(ValueError, match="list_key not found"):
        todo_task_mutations.apply_todo_task_mutation(
            fixture,
            lists,
            tasks,
            todo_task_mutations.TodoTaskMutationRequest(
                todo_task_mutations.TodoTaskAction.CREATE,
                "task-delta",
                "todo-missing",
                "Synthetic delta",
            ),
            readiness=_ready(),
        )
    with pytest.raises(ValueError, match="task_key not found"):
        todo_task_mutations.apply_todo_task_mutation(
            fixture,
            lists,
            tasks,
            todo_task_mutations.TodoTaskMutationRequest(
                todo_task_mutations.TodoTaskAction.UPDATE,
                "task-missing",
                "todo-default",
                "Missing",
            ),
            readiness=_ready(),
        )


def test_out104_remains_reserved_and_not_public() -> None:
    outlook = default_application_registry().get(ApplicationKey.OUTLOOK)
    assert outlook.state is ApplicationState.RESERVED
    assert default_tool_registry().by_application("outlook") == ()
