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
    todo_task_content,
    todo_task_reads,
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


def test_note_and_attachment_metadata_have_exact_read_back() -> None:
    fixture = mock_ui.default_outlook_fixture()
    _, tasks = todo_task_reads.default_synthetic_todo()
    notes, attachments, note = todo_task_content.apply_todo_content(
        fixture,
        tasks,
        (),
        (),
        todo_task_content.TodoContentRequest(
            todo_task_content.TodoContentAction.SET_NOTE,
            "task-alpha",
            note_text="Synthetic task note",
        ),
        readiness=_ready(),
    )
    assert note.note_read_back is not None
    assert note.note_read_back.text == "Synthetic task note"
    notes, attachments, added = todo_task_content.apply_todo_content(
        fixture,
        tasks,
        notes,
        attachments,
        todo_task_content.TodoContentRequest(
            todo_task_content.TodoContentAction.ADD_ATTACHMENT,
            "task-alpha",
            attachment_key="attach-alpha",
            file_name="evidence.txt",
            media_type="text/plain",
            size_bytes=128,
        ),
        readiness=_ready(),
    )
    assert added.attachment_read_back is not None
    assert added.attachment_read_back.file_name == "evidence.txt"
    notes, attachments, removed = todo_task_content.apply_todo_content(
        fixture,
        tasks,
        notes,
        attachments,
        todo_task_content.TodoContentRequest(
            todo_task_content.TodoContentAction.REMOVE_ATTACHMENT,
            "task-alpha",
            attachment_key="attach-alpha",
        ),
        readiness=_ready(),
    )
    assert attachments == ()
    assert removed.attachment_read_back is None
    notes, _, cleared = todo_task_content.apply_todo_content(
        fixture,
        tasks,
        notes,
        attachments,
        todo_task_content.TodoContentRequest(
            todo_task_content.TodoContentAction.CLEAR_NOTE,
            "task-alpha",
        ),
        readiness=_ready(),
    )
    assert notes == ()
    assert cleared.note_read_back is None


def test_attachment_add_is_idempotent() -> None:
    fixture = mock_ui.default_outlook_fixture()
    _, tasks = todo_task_reads.default_synthetic_todo()
    attachment = todo_task_content.SyntheticTodoAttachment(
        "attach-alpha",
        "task-alpha",
        "evidence.txt",
        "text/plain",
        128,
    )
    _, _, repeated = todo_task_content.apply_todo_content(
        fixture,
        tasks,
        (),
        (attachment,),
        todo_task_content.TodoContentRequest(
            todo_task_content.TodoContentAction.ADD_ATTACHMENT,
            "task-alpha",
            attachment_key="attach-alpha",
            file_name="evidence.txt",
            media_type="text/plain",
            size_bytes=128,
        ),
        readiness=_ready(),
    )
    assert repeated.changed is False


def test_content_rejects_locator_shape_and_unknown_task() -> None:
    with pytest.raises(ValueError, match="locator-free"):
        todo_task_content.TodoContentRequest(
            todo_task_content.TodoContentAction.ADD_ATTACHMENT,
            "task-alpha",
            attachment_key="attach-alpha",
            file_name="https://example.invalid/file.txt",
            media_type="text/plain",
            size_bytes=128,
        )
    fixture = mock_ui.default_outlook_fixture()
    _, tasks = todo_task_reads.default_synthetic_todo()
    with pytest.raises(ValueError, match="task_key not found"):
        todo_task_content.apply_todo_content(
            fixture,
            tasks,
            (),
            (),
            todo_task_content.TodoContentRequest(
                todo_task_content.TodoContentAction.SET_NOTE,
                "task-missing",
                note_text="Missing",
            ),
            readiness=_ready(),
        )


def test_out108_remains_reserved_and_not_public() -> None:
    outlook = default_application_registry().get(ApplicationKey.OUTLOOK)
    assert outlook.state is ApplicationState.RESERVED
    assert default_tool_registry().by_application("outlook") == ()
