"""Synthetic-only Outlook To Do notes/attachment metadata for OUT-108.

Attachment handling is metadata-only: no bytes, download locations, URLs,
selectors, sessions, tokens or live tenant material are accepted or produced.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from m365_mcp.apps.outlook.mock_ui import OutlookMockFixture
from m365_mcp.apps.outlook.readiness import OutlookReadinessReport
from m365_mcp.apps.outlook.todo_task_reads import SyntheticTodoTask

_MAX_NOTE_CHARS = 4000
_MAX_ATTACHMENTS_PER_TASK = 50
_MAX_ATTACHMENT_BYTES = 100_000_000


class TodoContentAction(StrEnum):
    SET_NOTE = "SET_NOTE"
    CLEAR_NOTE = "CLEAR_NOTE"
    ADD_ATTACHMENT = "ADD_ATTACHMENT"
    REMOVE_ATTACHMENT = "REMOVE_ATTACHMENT"


def _validate_key(name: str, value: str) -> None:
    if not value or value != value.strip() or "@" in value or any(
        char.isspace() for char in value
    ):
        raise ValueError(f"{name} must be an opaque semantic token")


@dataclass(frozen=True)
class SyntheticTodoNote:
    task_key: str
    text: str

    def __post_init__(self) -> None:
        _validate_key("task_key", self.task_key)
        if not self.text or self.text != self.text.strip():
            raise ValueError("note text must be non-empty and trimmed")
        if len(self.text) > _MAX_NOTE_CHARS:
            raise ValueError("note text exceeds bounded size")


@dataclass(frozen=True)
class SyntheticTodoAttachment:
    attachment_key: str
    task_key: str
    file_name: str
    media_type: str
    size_bytes: int

    def __post_init__(self) -> None:
        _validate_key("attachment_key", self.attachment_key)
        _validate_key("task_key", self.task_key)
        if (
            not self.file_name
            or self.file_name != self.file_name.strip()
            or "/" in self.file_name
            or "\\" in self.file_name
            or "://" in self.file_name
        ):
            raise ValueError("file_name must be locator-free basename metadata")
        if (
            not self.media_type
            or self.media_type != self.media_type.strip()
            or "://" in self.media_type
        ):
            raise ValueError("media_type must be locator-free metadata")
        if (
            isinstance(self.size_bytes, bool)
            or not 0 <= self.size_bytes <= _MAX_ATTACHMENT_BYTES
        ):
            raise ValueError("size_bytes outside bounded range")


@dataclass(frozen=True)
class TodoContentRequest:
    action: TodoContentAction
    task_key: str
    note_text: str | None = None
    attachment_key: str | None = None
    file_name: str | None = None
    media_type: str | None = None
    size_bytes: int | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.action, TodoContentAction):
            raise ValueError("action must be a closed TodoContentAction")
        _validate_key("task_key", self.task_key)
        if self.action is TodoContentAction.SET_NOTE:
            SyntheticTodoNote(self.task_key, self.note_text or "")
        elif self.action is TodoContentAction.ADD_ATTACHMENT:
            if self.attachment_key is None:
                raise ValueError("add attachment requires attachment_key")
            if self.file_name is None or self.media_type is None:
                raise ValueError("add attachment requires metadata")
            if self.size_bytes is None:
                raise ValueError("add attachment requires size_bytes")
            SyntheticTodoAttachment(
                self.attachment_key,
                self.task_key,
                self.file_name,
                self.media_type,
                self.size_bytes,
            )
        elif self.action is TodoContentAction.REMOVE_ATTACHMENT:
            if self.attachment_key is None:
                raise ValueError("remove attachment requires attachment_key")
            _validate_key("attachment_key", self.attachment_key)


@dataclass(frozen=True)
class TodoContentResult:
    action: TodoContentAction
    task_key: str
    changed: bool
    note_read_back: SyntheticTodoNote | None
    attachment_read_back: SyntheticTodoAttachment | None
    verified: bool
    synthetic: bool


def _gate(fixture: OutlookMockFixture, readiness: OutlookReadinessReport) -> None:
    if not fixture.synthetic:
        raise ValueError("OUT-108 fixture execution requires synthetic=true")
    if not readiness.ready_for_readonly_discovery:
        raise ValueError("Outlook read-only discovery is not ready")


def _validate_content(
    notes: tuple[SyntheticTodoNote, ...],
    attachments: tuple[SyntheticTodoAttachment, ...],
) -> None:
    note_keys = tuple(item.task_key for item in notes)
    if len(set(note_keys)) != len(note_keys):
        raise ValueError("at most one note is allowed per task")
    attachment_keys = tuple(item.attachment_key for item in attachments)
    if len(set(attachment_keys)) != len(attachment_keys):
        raise ValueError("attachment keys must be unique")
    counts: dict[str, int] = {}
    for item in attachments:
        counts[item.task_key] = counts.get(item.task_key, 0) + 1
        if counts[item.task_key] > _MAX_ATTACHMENTS_PER_TASK:
            raise ValueError("attachment count exceeds bounded size")


def apply_todo_content(
    fixture: OutlookMockFixture,
    tasks: tuple[SyntheticTodoTask, ...],
    notes: tuple[SyntheticTodoNote, ...],
    attachments: tuple[SyntheticTodoAttachment, ...],
    request: TodoContentRequest,
    *,
    readiness: OutlookReadinessReport,
) -> tuple[
    tuple[SyntheticTodoNote, ...],
    tuple[SyntheticTodoAttachment, ...],
    TodoContentResult,
]:
    """Apply one metadata-only task-content mutation with exact read-back."""
    _gate(fixture, readiness)
    _validate_content(notes, attachments)
    if not any(item.task_key == request.task_key for item in tasks):
        raise ValueError("synthetic task_key not found")
    existing_note = next(
        (item for item in notes if item.task_key == request.task_key),
        None,
    )

    expected_note = existing_note
    expected_attachment: SyntheticTodoAttachment | None = None
    changed = False

    if request.action is TodoContentAction.SET_NOTE:
        desired_note = SyntheticTodoNote(request.task_key, request.note_text or "")
        updated_notes = tuple(
            item for item in notes if item.task_key != request.task_key
        ) + (desired_note,)
        updated_attachments = attachments
        expected_note = desired_note
        changed = desired_note != existing_note
    elif request.action is TodoContentAction.CLEAR_NOTE:
        updated_notes = tuple(
            item for item in notes if item.task_key != request.task_key
        )
        updated_attachments = attachments
        expected_note = None
        changed = existing_note is not None
    elif request.action is TodoContentAction.ADD_ATTACHMENT:
        assert request.attachment_key is not None
        desired_attachment = SyntheticTodoAttachment(
            request.attachment_key,
            request.task_key,
            request.file_name or "",
            request.media_type or "",
            request.size_bytes if request.size_bytes is not None else -1,
        )
        existing_attachment = next(
            (
                item
                for item in attachments
                if item.attachment_key == request.attachment_key
            ),
            None,
        )
        if existing_attachment is None:
            count = sum(
                1 for item in attachments if item.task_key == request.task_key
            )
            if count >= _MAX_ATTACHMENTS_PER_TASK:
                raise ValueError("attachment count exceeds bounded size")
            updated_attachments = attachments + (desired_attachment,)
            changed = True
        elif existing_attachment == desired_attachment:
            updated_attachments = attachments
            changed = False
        else:
            raise ValueError("attachment_key already exists with different metadata")
        updated_notes = notes
        expected_attachment = desired_attachment
    elif request.action is TodoContentAction.REMOVE_ATTACHMENT:
        assert request.attachment_key is not None
        existing_attachment = next(
            (
                item
                for item in attachments
                if item.attachment_key == request.attachment_key
            ),
            None,
        )
        if (
            existing_attachment is not None
            and existing_attachment.task_key != request.task_key
        ):
            raise ValueError("attachment_key belongs to a different synthetic task")
        updated_attachments = tuple(
            item
            for item in attachments
            if item.attachment_key != request.attachment_key
        )
        updated_notes = notes
        changed = existing_attachment is not None
    else:
        raise ValueError("unsupported content mutation")

    updated_notes = tuple(sorted(updated_notes, key=lambda item: item.task_key))
    updated_attachments = tuple(
        sorted(updated_attachments, key=lambda item: item.attachment_key)
    )
    _validate_content(updated_notes, updated_attachments)
    note_read_back = next(
        (item for item in updated_notes if item.task_key == request.task_key),
        None,
    )
    attachment_read_back = (
        next(
            (
                item
                for item in updated_attachments
                if item.attachment_key == request.attachment_key
            ),
            None,
        )
        if request.attachment_key is not None
        else None
    )
    if note_read_back != expected_note:
        raise RuntimeError("note read-back did not prove requested state")
    if attachment_read_back != expected_attachment:
        raise RuntimeError("attachment read-back did not prove requested state")
    return updated_notes, updated_attachments, TodoContentResult(
        action=request.action,
        task_key=request.task_key,
        changed=changed,
        note_read_back=note_read_back,
        attachment_read_back=attachment_read_back,
        verified=True,
        synthetic=True,
    )


__all__ = [
    "SyntheticTodoAttachment",
    "SyntheticTodoNote",
    "TodoContentAction",
    "TodoContentRequest",
    "TodoContentResult",
    "apply_todo_content",
]
