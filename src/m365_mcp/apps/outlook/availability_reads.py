"""Synthetic-only Outlook availability/free-busy reads for OUT-022.

Availability is derived exclusively from the OUT-021 synthetic event model over
the OUT-020 calendar catalog. Time remains relative: a query window is a day
offset plus a minute-of-day range, and every produced slot is a relative
interval. No absolute timestamp, timezone, working-hours tenant setting,
attendee address or live free-busy lookup is introduced.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from m365_mcp.apps.outlook.calendar_events import (
    EventShowAs,
    SyntheticEvent,
    list_fixture_events,
)
from m365_mcp.apps.outlook.calendar_list import SyntheticCalendar
from m365_mcp.apps.outlook.mock_ui import OutlookMockFixture
from m365_mcp.apps.outlook.readiness import OutlookReadinessReport

_MIN_DAY_OFFSET = -3650
_MAX_DAY_OFFSET = 3650
_MINUTES_PER_DAY = 1440
_MAX_WINDOW_DAYS = 31
_MIN_SLOT_MINUTES = 5


class AvailabilityState(StrEnum):
    """Closed availability states derived from overlapping event presentation."""

    FREE = "FREE"
    TENTATIVE = "TENTATIVE"
    BUSY = "BUSY"
    OUT_OF_OFFICE = "OUT_OF_OFFICE"


_STATE_RANK: dict[AvailabilityState, int] = {
    AvailabilityState.FREE: 0,
    AvailabilityState.TENTATIVE: 1,
    AvailabilityState.BUSY: 2,
    AvailabilityState.OUT_OF_OFFICE: 3,
}

_SHOW_AS_TO_STATE: dict[EventShowAs, AvailabilityState] = {
    EventShowAs.FREE: AvailabilityState.FREE,
    EventShowAs.TENTATIVE: AvailabilityState.TENTATIVE,
    EventShowAs.BUSY: AvailabilityState.BUSY,
    EventShowAs.OUT_OF_OFFICE: AvailabilityState.OUT_OF_OFFICE,
}


@dataclass(frozen=True)
class AvailabilityWindow:
    """Closed bounded relative query window for a free-busy read."""

    from_day_offset: int
    to_day_offset: int
    day_start_minute: int = 0
    day_end_minute: int = _MINUTES_PER_DAY
    slot_minutes: int = 30

    def __post_init__(self) -> None:
        for field_name in (
            "from_day_offset",
            "to_day_offset",
            "day_start_minute",
            "day_end_minute",
            "slot_minutes",
        ):
            value = getattr(self, field_name)
            if not isinstance(value, int) or isinstance(value, bool):
                raise ValueError(f"{field_name} must be an integer")

        for field_name in ("from_day_offset", "to_day_offset"):
            value = getattr(self, field_name)
            if not _MIN_DAY_OFFSET <= value <= _MAX_DAY_OFFSET:
                raise ValueError(f"{field_name} exceeds the bounded day-offset window")
        if self.from_day_offset > self.to_day_offset:
            raise ValueError("from_day_offset must not exceed to_day_offset")
        if self.to_day_offset - self.from_day_offset + 1 > _MAX_WINDOW_DAYS:
            raise ValueError("availability window exceeds the bounded day count")

        if not 0 <= self.day_start_minute < _MINUTES_PER_DAY:
            raise ValueError("day_start_minute must fall inside a single day")
        if not 0 < self.day_end_minute <= _MINUTES_PER_DAY:
            raise ValueError("day_end_minute must fall inside a single day")
        if self.day_start_minute >= self.day_end_minute:
            raise ValueError("day_start_minute must precede day_end_minute")

        if self.slot_minutes < _MIN_SLOT_MINUTES:
            raise ValueError(f"slot_minutes must be at least {_MIN_SLOT_MINUTES}")
        span = self.day_end_minute - self.day_start_minute
        if self.slot_minutes > span:
            raise ValueError("slot_minutes must not exceed the daily window span")
        if span % self.slot_minutes != 0:
            raise ValueError("daily window span must be a whole multiple of slot_minutes")


@dataclass(frozen=True)
class AvailabilitySlot:
    """One bounded relative availability slot."""

    day_offset: int
    start_minute_of_day: int
    end_minute_of_day: int
    state: AvailabilityState
    overlapping_event_count: int
    synthetic: bool

    def to_projection(self) -> dict[str, object]:
        return {
            "day_offset": self.day_offset,
            "start_minute_of_day": self.start_minute_of_day,
            "end_minute_of_day": self.end_minute_of_day,
            "state": self.state.value,
            "overlapping_event_count": self.overlapping_event_count,
            "synthetic": self.synthetic,
        }


@dataclass(frozen=True)
class AvailabilityResult:
    """Deterministic free-busy projection across a bounded relative window."""

    slots: tuple[AvailabilitySlot, ...]
    calendar_key: str | None
    slot_count: int
    free_slot_count: int
    busy_slot_count: int
    synthetic: bool


def _absolute(day_offset: int, minute_of_day: int) -> int:
    return day_offset * _MINUTES_PER_DAY + minute_of_day


def read_fixture_availability(
    fixture: OutlookMockFixture,
    window: AvailabilityWindow,
    *,
    readiness: OutlookReadinessReport,
    calendar_key: str | None = None,
    events: tuple[SyntheticEvent, ...] | None = None,
    calendars: tuple[SyntheticCalendar, ...] | None = None,
) -> AvailabilityResult:
    """Derive bounded free-busy slots from synthetic events, failing closed."""
    if not isinstance(window, AvailabilityWindow):
        raise ValueError("window must be a bounded AvailabilityWindow")

    # OUT-021 re-executes the OUT-020 calendar gate and the readiness/synthetic
    # gates, so availability cannot bypass any predecessor boundary.
    listing = list_fixture_events(
        fixture,
        readiness=readiness,
        calendar_key=calendar_key,
        events=events,
        calendars=calendars,
    )

    intervals = tuple(
        (
            _absolute(item.start_day_offset, item.start_minute_of_day),
            _absolute(item.end_day_offset, item.end_minute_of_day),
            _SHOW_AS_TO_STATE[item.show_as],
        )
        for item in listing.items
    )

    slots: list[AvailabilitySlot] = []
    for day_offset in range(window.from_day_offset, window.to_day_offset + 1):
        minute = window.day_start_minute
        while minute < window.day_end_minute:
            slot_start = _absolute(day_offset, minute)
            slot_end = slot_start + window.slot_minutes
            overlapping = tuple(
                state
                for start, end, state in intervals
                if start < slot_end and end > slot_start
            )
            blocking = tuple(
                state for state in overlapping if state is not AvailabilityState.FREE
            )
            state = (
                max(blocking, key=lambda item: _STATE_RANK[item])
                if blocking
                else AvailabilityState.FREE
            )
            slots.append(
                AvailabilitySlot(
                    day_offset=day_offset,
                    start_minute_of_day=minute,
                    end_minute_of_day=minute + window.slot_minutes,
                    state=state,
                    overlapping_event_count=len(overlapping),
                    synthetic=True,
                )
            )
            minute += window.slot_minutes

    frozen_slots = tuple(slots)
    return AvailabilityResult(
        slots=frozen_slots,
        calendar_key=calendar_key,
        slot_count=len(frozen_slots),
        free_slot_count=sum(
            1 for slot in frozen_slots if slot.state is AvailabilityState.FREE
        ),
        busy_slot_count=sum(
            1 for slot in frozen_slots if slot.state is not AvailabilityState.FREE
        ),
        synthetic=True,
    )


__all__ = [
    "AvailabilityResult",
    "AvailabilitySlot",
    "AvailabilityState",
    "AvailabilityWindow",
    "read_fixture_availability",
]
