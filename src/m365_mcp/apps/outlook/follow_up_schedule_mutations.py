"""Synthetic-only Outlook follow-up due/reminder semantics for OUT-034.

The operation updates only synthetic FollowUpFlag scheduling metadata and
verifies start, due and reminder values through OUT-018 read-back. Outlook
remains RESERVED; no public mutation or browser primitive is exposed.
"""

from __future__ import annotations

from dataclasses import dataclass

from m365_mcp.apps.outlook.follow_up_reads import (
    FollowUpFlag,
    FollowUpState,
    read_fixture_follow_up_state,
)
from m365_mcp.apps.outlook.mock_ui import OutlookMockFixture
from m365_mcp.apps.outlook.readiness import OutlookReadinessReport

_MIN_DAY_OFFSET = -3650
_MAX_DAY_OFFSET = 3650


@dataclass(frozen=True)
class FollowUpScheduleMutationRequest:
    message_key: str
    due_day_offset: int
    start_day_offset: int | None = None
    reminder_day_offset: int | None = None

    def __post_init__(self) -> None:
        invalid_key = (
            not self.message_key
            or self.message_key != self.message_key.strip()
            or any(char.isspace() for char in self.message_key)
        )
        if invalid_key:
            raise ValueError("message_key must be a non-empty semantic token")

        for field_name in (
            "due_day_offset",
            "start_day_offset",
            "reminder_day_offset",
        ):
            value = getattr(self, field_name)
            if value is None:
                continue
            if isinstance(value, bool) or not _MIN_DAY_OFFSET <= value <= _MAX_DAY_OFFSET:
                raise ValueError(f"{field_name} exceeds bounded day-offset window")

        if (
            self.start_day_offset is not None
            and self.due_day_offset < self.start_day_offset
        ):
            raise ValueError("due_day_offset must not precede start_day_offset")
        if (
            self.reminder_day_offset is not None
            and self.start_day_offset is not None
            and self.reminder_day_offset < self.start_day_offset
        ):
            raise ValueError("reminder_day_offset must not precede start_day_offset")
        if (
            self.reminder_day_offset is not None
            and self.reminder_day_offset > self.due_day_offset
        ):
            raise ValueError("reminder_day_offset must not follow due_day_offset")

    def to_payload(self) -> dict[str, object]:
        payload: dict[str, object] = {
            "message_key": self.message_key,
            "due_day_offset": self.due_day_offset,
        }
        if self.start_day_offset is not None:
            payload["start_day_offset"] = self.start_day_offset
        if self.reminder_day_offset is not None:
            payload["reminder_day_offset"] = self.reminder_day_offset
        return payload


@dataclass(frozen=True)
class FollowUpScheduleMutationResult:
    message_key: str
    changed: bool
    read_back_start_day_offset: int | None
    read_back_due_day_offset: int | None
    read_back_reminder_day_offset: int | None
    verified: bool
    synthetic: bool = True


def apply_fixture_follow_up_schedule(
    fixture: OutlookMockFixture,
    request: FollowUpScheduleMutationRequest,
    *,
    readiness: OutlookReadinessReport,
    flags: tuple[FollowUpFlag, ...],
) -> tuple[tuple[FollowUpFlag, ...], FollowUpScheduleMutationResult]:
    """Apply one synthetic schedule update and verify all scheduled fields."""
    if not fixture.synthetic:
        raise ValueError("OUT-034 fixture execution requires synthetic=true")
    if not readiness.ready_for_readonly_discovery:
        raise ValueError("Outlook read-only discovery is not ready")
    if not any(message.message_key == request.message_key for message in fixture.messages):
        raise ValueError("synthetic message_key not found")

    current = next(
        (item for item in flags if item.message_key == request.message_key),
        None,
    )
    if current is None or current.state is not FollowUpState.FLAGGED:
        raise ValueError("follow-up schedule requires an existing flagged message")

    replacement = FollowUpFlag(
        message_key=current.message_key,
        state=FollowUpState.FLAGGED,
        start_day_offset=(
            current.start_day_offset
            if request.start_day_offset is None
            else request.start_day_offset
        ),
        due_day_offset=request.due_day_offset,
        reminder_day_offset=request.reminder_day_offset,
    )
    updated = tuple(
        replacement if item.message_key == request.message_key else item
        for item in flags
    )
    read_back = read_fixture_follow_up_state(
        fixture,
        request.message_key,
        readiness=readiness,
        flags=updated,
    )
    verified = (
        read_back.start_day_offset == replacement.start_day_offset
        and read_back.due_day_offset == replacement.due_day_offset
        and read_back.reminder_day_offset == replacement.reminder_day_offset
    )
    if not verified:
        raise RuntimeError("synthetic follow-up schedule read-back did not match")

    return (
        updated,
        FollowUpScheduleMutationResult(
            message_key=request.message_key,
            changed=current != replacement,
            read_back_start_day_offset=read_back.start_day_offset,
            read_back_due_day_offset=read_back.due_day_offset,
            read_back_reminder_day_offset=read_back.reminder_day_offset,
            verified=True,
        ),
    )


__all__ = [
    "FollowUpScheduleMutationRequest",
    "FollowUpScheduleMutationResult",
    "apply_fixture_follow_up_schedule",
]
