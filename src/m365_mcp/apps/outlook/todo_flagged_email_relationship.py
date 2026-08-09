"""Synthetic-only flagged-email to To Do task relationship for OUT-109."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from m365_mcp.apps.outlook.follow_up_reads import (
    FollowUpFlag,
    FollowUpState,
    read_fixture_follow_up_state,
)
from m365_mcp.apps.outlook.mock_ui import OutlookMockFixture
from m365_mcp.apps.outlook.readiness import OutlookReadinessReport
from m365_mcp.apps.outlook.todo_task_reads import SyntheticTodoTask


class FlaggedEmailTaskAction(StrEnum):
    LINK = "LINK"
    UNLINK = "UNLINK"


def _validate_key(name: str, value: str) -> None:
    if not value or value != value.strip() or "@" in value or any(
        char.isspace() for char in value
    ):
        raise ValueError(f"{name} must be an opaque semantic token")


@dataclass(frozen=True)
class FlaggedEmailTaskLink:
    message_key: str
    task_key: str

    def __post_init__(self) -> None:
        _validate_key("message_key", self.message_key)
        _validate_key("task_key", self.task_key)


@dataclass(frozen=True)
class FlaggedEmailTaskRequest:
    action: FlaggedEmailTaskAction
    message_key: str
    task_key: str

    def __post_init__(self) -> None:
        if not isinstance(self.action, FlaggedEmailTaskAction):
            raise ValueError("action must be a closed FlaggedEmailTaskAction")
        _validate_key("message_key", self.message_key)
        _validate_key("task_key", self.task_key)


@dataclass(frozen=True)
class FlaggedEmailTaskResult:
    action: FlaggedEmailTaskAction
    message_key: str
    task_key: str
    changed: bool
    read_back: FlaggedEmailTaskLink | None
    verified: bool
    synthetic: bool


def _gate(fixture: OutlookMockFixture, readiness: OutlookReadinessReport) -> None:
    if not fixture.synthetic:
        raise ValueError("OUT-109 fixture execution requires synthetic=true")
    if not readiness.ready_for_readonly_discovery:
        raise ValueError("Outlook read-only discovery is not ready")


def _validate_links(links: tuple[FlaggedEmailTaskLink, ...]) -> None:
    message_keys = tuple(item.message_key for item in links)
    if len(set(message_keys)) != len(message_keys):
        raise ValueError("message_key may link to at most one synthetic task")


def apply_flagged_email_task_relationship(
    fixture: OutlookMockFixture,
    tasks: tuple[SyntheticTodoTask, ...],
    links: tuple[FlaggedEmailTaskLink, ...],
    request: FlaggedEmailTaskRequest,
    *,
    readiness: OutlookReadinessReport,
    flags: tuple[FollowUpFlag, ...] | None = None,
) -> tuple[tuple[FlaggedEmailTaskLink, ...], FlaggedEmailTaskResult]:
    """Link or unlink a currently flagged synthetic message and task."""
    _gate(fixture, readiness)
    _validate_links(links)
    if not any(item.task_key == request.task_key for item in tasks):
        raise ValueError("synthetic task_key not found")
    follow_up = read_fixture_follow_up_state(
        fixture,
        request.message_key,
        readiness=readiness,
        flags=flags,
    )
    existing = next(
        (item for item in links if item.message_key == request.message_key),
        None,
    )

    if request.action is FlaggedEmailTaskAction.LINK:
        if follow_up.state is not FollowUpState.FLAGGED:
            raise ValueError("message must have flagged follow-up state")
        desired = FlaggedEmailTaskLink(request.message_key, request.task_key)
        if existing is None:
            updated = links + (desired,)
            changed = True
        elif existing == desired:
            updated = links
            changed = False
        else:
            raise ValueError("message_key is already linked to a different task")
        expected: FlaggedEmailTaskLink | None = desired
    elif request.action is FlaggedEmailTaskAction.UNLINK:
        if existing is not None and existing.task_key != request.task_key:
            raise ValueError("message_key is linked to a different task")
        updated = tuple(
            item for item in links if item.message_key != request.message_key
        )
        changed = existing is not None
        expected = None
    else:
        raise ValueError("unsupported flagged-email relationship mutation")

    updated = tuple(sorted(updated, key=lambda item: item.message_key))
    _validate_links(updated)
    read_back = next(
        (item for item in updated if item.message_key == request.message_key),
        None,
    )
    if read_back != expected:
        raise RuntimeError("relationship read-back did not prove requested state")
    return updated, FlaggedEmailTaskResult(
        action=request.action,
        message_key=request.message_key,
        task_key=request.task_key,
        changed=changed,
        read_back=read_back,
        verified=True,
        synthetic=True,
    )


__all__ = [
    "FlaggedEmailTaskAction",
    "FlaggedEmailTaskLink",
    "FlaggedEmailTaskRequest",
    "FlaggedEmailTaskResult",
    "apply_flagged_email_task_relationship",
]
