"""Synthetic reminder/category/private/show-as options for OUT-085."""

from __future__ import annotations

from dataclasses import dataclass, replace

from m365_mcp.apps.outlook.calendar_events import (
    EventSensitivity,
    EventShowAs,
    SyntheticEvent,
)
from m365_mcp.apps.outlook.readiness import OutlookReadinessReport

_MAX_CATEGORIES = 25
_MAX_REMINDER_MINUTES = 60 * 24 * 14


@dataclass(frozen=True)
class SyntheticCalendarEventOptions:
    event_key: str
    reminder_minutes_before: int | None = None
    category_keys: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _validate_key("event_key", self.event_key)
        if self.reminder_minutes_before is not None:
            value = self.reminder_minutes_before
            if not isinstance(value, int) or isinstance(value, bool):
                raise ValueError("reminder_minutes_before must be an integer")
            if not 0 <= value <= _MAX_REMINDER_MINUTES:
                raise ValueError("reminder exceeds the bounded synthetic range")
        if len(self.category_keys) > _MAX_CATEGORIES:
            raise ValueError("category_keys exceeds bounded size")
        if len(self.category_keys) != len(set(self.category_keys)):
            raise ValueError("category_keys must be unique")
        for category_key in self.category_keys:
            _validate_key("category_key", category_key)


@dataclass(frozen=True)
class CalendarEventOptionsRequest:
    event_key: str
    reminder_minutes_before: int | None
    category_keys: tuple[str, ...]
    private: bool
    show_as: EventShowAs

    def __post_init__(self) -> None:
        _validate_key("event_key", self.event_key)
        if not isinstance(self.private, bool):
            raise ValueError("private must be a boolean")
        SyntheticCalendarEventOptions(
            event_key=self.event_key,
            reminder_minutes_before=self.reminder_minutes_before,
            category_keys=self.category_keys,
        )

    def to_payload(self) -> dict[str, object]:
        return {
            "event_key": self.event_key,
            "reminder_minutes_before": self.reminder_minutes_before,
            "category_keys": self.category_keys,
            "private": self.private,
            "show_as": self.show_as.value,
        }


@dataclass(frozen=True)
class CalendarEventOptionsResult:
    event_key: str
    changed: bool
    verified: bool
    read_back_event: SyntheticEvent
    read_back_options: SyntheticCalendarEventOptions
    synthetic: bool = True


def _validate_key(name: str, value: str) -> None:
    if not value or value != value.strip() or any(char.isspace() for char in value):
        raise ValueError(f"{name} must be a non-empty semantic token")


def mutate_calendar_event_options(
    events: tuple[SyntheticEvent, ...],
    options: tuple[SyntheticCalendarEventOptions, ...],
    request: CalendarEventOptionsRequest,
    *,
    readiness: OutlookReadinessReport,
) -> tuple[
    tuple[SyntheticEvent, ...],
    tuple[SyntheticCalendarEventOptions, ...],
    CalendarEventOptionsResult,
]:
    """Apply bounded synthetic event options with exact read-back."""
    if not readiness.ready_for_readonly_discovery:
        raise ValueError("Outlook read-only discovery is not ready")
    current_event = next(
        (item for item in events if item.event_key == request.event_key),
        None,
    )
    if current_event is None:
        raise ValueError("event_key must reference an existing synthetic event")

    replacement_event = replace(
        current_event,
        sensitivity=(
            EventSensitivity.PRIVATE if request.private else EventSensitivity.NORMAL
        ),
        show_as=request.show_as,
    )
    replacement_options = SyntheticCalendarEventOptions(
        event_key=request.event_key,
        reminder_minutes_before=request.reminder_minutes_before,
        category_keys=request.category_keys,
    )
    current_options = next(
        (item for item in options if item.event_key == request.event_key),
        None,
    )
    option_keys = tuple(item.event_key for item in options)
    if len(option_keys) != len(set(option_keys)):
        raise ValueError("event options contain duplicate event_key values")

    updated_events = tuple(
        replacement_event if item.event_key == request.event_key else item
        for item in events
    )
    if current_options is None:
        updated_options = (*options, replacement_options)
    else:
        updated_options = tuple(
            replacement_options if item.event_key == request.event_key else item
            for item in options
        )

    read_back_event = next(
        item for item in updated_events if item.event_key == request.event_key
    )
    read_back_options = next(
        item for item in updated_options if item.event_key == request.event_key
    )
    if read_back_event != replacement_event or read_back_options != replacement_options:
        raise RuntimeError("synthetic read-back did not prove calendar event options")

    return updated_events, updated_options, CalendarEventOptionsResult(
        event_key=request.event_key,
        changed=(
            current_event != replacement_event or current_options != replacement_options
        ),
        verified=True,
        read_back_event=read_back_event,
        read_back_options=read_back_options,
    )


__all__ = [
    "CalendarEventOptionsRequest",
    "CalendarEventOptionsResult",
    "SyntheticCalendarEventOptions",
    "mutate_calendar_event_options",
]
