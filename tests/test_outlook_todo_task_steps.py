from __future__ import annotations

import pytest

from m365_mcp.application_registry import (
    ApplicationKey,
    ApplicationState,
    default_application_registry,
)
from m365_mcp.apps.outlook import (
    mock_ui,
    readiness,
    todo_task_reads,
    todo_task_steps,
)
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


def test_step_add_update_complete_delete_have_exact_read_back() -> None:
    fixture = mock_ui.default_outlook_fixture()
    _, tasks = todo_task_reads.default_synthetic_todo()
    steps, added = todo_task_steps.apply_todo_step(
        fixture,
        tasks,
        (),
        todo_task_steps.TodoStepRequest(
            todo_task_steps.TodoStepAction.ADD,
            "task-alpha",
            "step-alpha-1",
            "Draft synthetic outline",
        ),
        readiness=_ready(),
    )
    assert added.read_back is not None
    steps, updated = todo_task_steps.apply_todo_step(
        fixture,
        tasks,
        steps,
        todo_task_steps.TodoStepRequest(
            todo_task_steps.TodoStepAction.UPDATE,
            "task-alpha",
            "step-alpha-1",
            "Draft revised outline",
        ),
        readiness=_ready(),
    )
    assert updated.read_back is not None
    assert updated.read_back.title == "Draft revised outline"
    steps, completed = todo_task_steps.apply_todo_step(
        fixture,
        tasks,
        steps,
        todo_task_steps.TodoStepRequest(
            todo_task_steps.TodoStepAction.COMPLETE,
            "task-alpha",
            "step-alpha-1",
        ),
        readiness=_ready(),
    )
    assert completed.read_back is not None
    assert completed.read_back.completed is True
    steps, deleted = todo_task_steps.apply_todo_step(
        fixture,
        tasks,
        steps,
        todo_task_steps.TodoStepRequest(
            todo_task_steps.TodoStepAction.DELETE,
            "task-alpha",
            "step-alpha-1",
        ),
        readiness=_ready(),
    )
    assert steps == ()
    assert deleted.read_back is None


def test_step_add_and_delete_are_idempotent() -> None:
    fixture = mock_ui.default_outlook_fixture()
    _, tasks = todo_task_reads.default_synthetic_todo()
    step = todo_task_steps.SyntheticTodoStep(
        "step-alpha-1",
        "task-alpha",
        "Draft synthetic outline",
    )
    _, repeated = todo_task_steps.apply_todo_step(
        fixture,
        tasks,
        (step,),
        todo_task_steps.TodoStepRequest(
            todo_task_steps.TodoStepAction.ADD,
            "task-alpha",
            "step-alpha-1",
            "Draft synthetic outline",
        ),
        readiness=_ready(),
    )
    assert repeated.changed is False
    _, absent = todo_task_steps.apply_todo_step(
        fixture,
        tasks,
        (),
        todo_task_steps.TodoStepRequest(
            todo_task_steps.TodoStepAction.DELETE,
            "task-alpha",
            "step-missing",
        ),
        readiness=_ready(),
    )
    assert absent.changed is False


def test_step_mutation_fails_closed_for_unknown_task_and_conflict() -> None:
    fixture = mock_ui.default_outlook_fixture()
    _, tasks = todo_task_reads.default_synthetic_todo()
    with pytest.raises(ValueError, match="task_key not found"):
        todo_task_steps.apply_todo_step(
            fixture,
            tasks,
            (),
            todo_task_steps.TodoStepRequest(
                todo_task_steps.TodoStepAction.ADD,
                "task-missing",
                "step-alpha-1",
                "Missing",
            ),
            readiness=_ready(),
        )
    existing = todo_task_steps.SyntheticTodoStep(
        "step-alpha-1",
        "task-alpha",
        "Existing",
    )
    with pytest.raises(ValueError, match="different state"):
        todo_task_steps.apply_todo_step(
            fixture,
            tasks,
            (existing,),
            todo_task_steps.TodoStepRequest(
                todo_task_steps.TodoStepAction.ADD,
                "task-alpha",
                "step-alpha-1",
                "Different",
            ),
            readiness=_ready(),
        )


def test_out107_remains_reserved_and_not_public() -> None:
    outlook = default_application_registry().get(ApplicationKey.OUTLOOK)
    assert outlook.state is ApplicationState.RESERVED
    assert default_tool_registry().by_application("outlook") == ()
