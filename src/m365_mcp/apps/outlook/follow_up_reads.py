"""Synthetic-only Outlook flag/follow-up read state for OUT-018.

Follow-up scheduling is modelled with deterministic relative day offsets rather
than absolute timestamps, so the model stays tenant-neutral, timezone-free and
reproducible. It performs no mutation and exposes no browser primitive.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from m365_mcp.apps.outlook.mock_ui import OutlookMockFixture
from m365_mcp.apps.outlook.readiness import OutlookReadinessReport

_MIN_DAY_OFFSET = -3650
_MAX_DAY_OFFSET = 3650


class FollowUpState(StrEnum):
    """Closed follow-up states covering the read-only lifecycle."""

    NOT_FLAGGED = "NOT_FLAGGED"
    FLAGGED = "FLAGGED"
    COMPLETED = "COMPLETED"


@dataclass(frozen=True)
class FollowUpFlag:
    """Tenant-neutral follow-up flag bound to one synthetic message."""

    message_key: str
    state: FollowUpState
    start_day_offset: int | None = None
    due_day_offset: int | None = None
    completed_day_offset: int | None = None

    def __post_init__(self) -> None:
        invalid_key = (
            not self.message_key
            or self.message_key != self.message_key.strip()
            or any(char.isspace() for char in self.message_key)
        )
        if invalid_key:
            raise ValueError("message_key must be a non-empty semantic token")
        if not isinstance(self.state, FollowUpState):
            raise ValueError("state must be a closed FollowUpState")

        for field_name in ("start_day_offset", "due_day_offset", "completed_day_offset"):
            value = getattr(self, field_name)
            if value is None:
                continue
            if not isinstance(value, int) or isinstance(value, bool):
                raise ValueError(f"{field_name} must be an integer day offset")
            if not _MIN_DAY_OFFSET <= value <= _MAX_DAY_OFFSET:
                raise ValueError(f"{field_name} exceeds the bounded day-offset window")

        if self.state is FollowUpState.NOT_FLAGGED and (
            self.start_day_offset is not None
            or self.due_day_offset is not None
            or self.completed_day_offset is not None
        ):
            raise ValueError("an unflagged message must not carry follow-up scheduling")
        if self.state is FollowUpState.COMPLETED and self.completed_day_offset is None:
            raise ValueError("a completed follow-up requires completed_day_offset")
        if self.state is not FollowUpState.COMPLETED and self.completed_day_offset is not None:
            raise ValueError("completed_day_offset is only valid for a completed follow-up")
        if (
            self.start_day_offset is not None
            and self.due_day_offset is not None
            and self.due_day_offset < self.start_day_offset
        ):
            raise ValueError("due_day_offset must not precede start_day_offset")


@dataclass(frozen=True)
class FollowUpReadState:
    """Read-only follow-up projection for one synthetic message."""

    message_key: str
    state: FollowUpState
    is_flagged: bool
    is_completed: bool
    start_day_offset: int | None
    due_day_offset: int | None
    completed_day_offset: int | None
    synthetic: bool

    def to_projection(self) -> dict[str, object]:
        return {
            "message_key": self.message_key,
            "state": self.state.value,
            "is_flagged": self.is_flagged,
            "is_completed": self.is_completed,
            "start_day_offset": self.start_day_offset,
            "due_day_offset": self.due_day_offset,
            "completed_day_offset": self.completed_day_offset,
            "synthetic": self.synthetic,
        }


@dataclass(frozen=True)
class FollowUpListResult:
    """Deterministic bounded follow-up listing across the synthetic fixture."""

    items: tuple[FollowUpReadState, ...]
    flagged_count: int
    completed_count: int
    overdue_count: int
    synthetic: bool


def default_synthetic_follow_up_flags() -> tuple[FollowUpFlag, ...]:
    """Return the explicit synthetic follow-up catalog."""
    return (
        FollowUpFlag(
            message_key="msg-001",
            state=FollowUpState.FLAGGED,
            start_day_offset=0,
            due_day_offset=2,
        ),
        FollowUpFlag(
            message_key="msg-002",
            state=FollowUpState.COMPLETED,
            start_day_offset=-5,
            due_day_offset=-1,
            completed_day_offset=-1,
        ),
    )


def _validate(
    fixture: OutlookMockFixture,
    flags: tuple[FollowUpFlag, ...],
) -> None:
    keys = tuple(flag.message_key for flag in flags)
    if len(set(keys)) != len(keys):
        raise ValueError("follow-up flags must be unique per message_key")
    known = {message.message_key for message in fixture.messages}
    for flag in flags:
        if flag.message_key not in known:
            raise ValueError("follow-up flag references unknown synthetic message_key")


def _project(flag: FollowUpFlag) -> FollowUpReadState:
    return FollowUpReadState(
        message_key=flag.message_key,
        state=flag.state,
        is_flagged=flag.state is FollowUpState.FLAGGED,
        is_completed=flag.state is FollowUpState.COMPLETED,
        start_day_offset=flag.start_day_offset,
        due_day_offset=flag.due_day_offset,
        completed_day_offset=flag.completed_day_offset,
        synthetic=True,
    )


def read_fixture_follow_up_state(
    fixture: OutlookMockFixture,
    message_key: str,
    *,
    readiness: OutlookReadinessReport,
    flags: tuple[FollowUpFlag, ...] | None = None,
) -> FollowUpReadState:
    """Read follow-up state for one synthetic message, defaulting to unflagged."""
    if not message_key or message_key != message_key.strip():
        raise ValueError("message_key must be a non-empty semantic token")
    if not fixture.synthetic:
        raise ValueError("OUT-018 fixture execution requires synthetic=true")
    if not readiness.ready_for_readonly_discovery:
        raise ValueError("Outlook read-only discovery is not ready")
    if not any(message.message_key == message_key for message in fixture.messages):
        raise ValueError("synthetic message_key not found")

    catalog = default_synthetic_follow_up_flags() if flags is None else flags
    _validate(fixture, catalog)

    match = next((flag for flag in catalog if flag.message_key == message_key), None)
    if match is None:
        return _project(FollowUpFlag(message_key=message_key, state=FollowUpState.NOT_FLAGGED))
    return _project(match)


def list_fixture_follow_up_state(
    fixture: OutlookMockFixture,
    *,
    readiness: OutlookReadinessReport,
    flags: tuple[FollowUpFlag, ...] | None = None,
    reference_day_offset: int = 0,
) -> FollowUpListResult:
    """List follow-up state for every synthetic message with bounded counters."""
    if not fixture.synthetic:
        raise ValueError("OUT-018 fixture execution requires synthetic=true")
    if not readiness.ready_for_readonly_discovery:
        raise ValueError("Outlook read-only discovery is not ready")
    if not _MIN_DAY_OFFSET <= reference_day_offset <= _MAX_DAY_OFFSET:
        raise ValueError("reference_day_offset exceeds the bounded day-offset window")

    catalog = default_synthetic_follow_up_flags() if flags is None else flags
    _validate(fixture, catalog)

    by_key = {flag.message_key: flag for flag in catalog}
    items = tuple(
        _project(
            by_key.get(
                message.message_key,
                FollowUpFlag(
                    message_key=message.message_key,
                    state=FollowUpState.NOT_FLAGGED,
                ),
            )
        )
        for message in fixture.messages
    )
    overdue = sum(
        1
        for item in items
        if item.is_flagged
        and item.due_day_offset is not None
        and item.due_day_offset < reference_day_offset
    )
    return FollowUpListResult(
        items=items,
        flagged_count=sum(1 for item in items if item.is_flagged),
        completed_count=sum(1 for item in items if item.is_completed),
        overdue_count=overdue,
        synthetic=True,
    )


__all__ = [
    "FollowUpFlag",
    "FollowUpListResult",
    "FollowUpReadState",
    "FollowUpState",
    "default_synthetic_follow_up_flags",
    "list_fixture_follow_up_state",
    "read_fixture_follow_up_state",
]
