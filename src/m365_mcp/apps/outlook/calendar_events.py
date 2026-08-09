"""Synthetic-only Outlook calendar event list/get/search for OUT-021.

Events are modelled as bounded, tenant-neutral synthetic records attached to
the OUT-020 calendar catalog. Time is expressed exclusively as relative integer
day offsets plus minute-of-day, consistent with OUT-018/OUT-019, so results are
deterministic and no absolute timestamp, timezone or wall-clock read is
introduced. Mutation, invitations and responses are out of scope.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from m365_mcp.apps.outlook.calendar_list import (
    SyntheticCalendar,
    default_synthetic_calendars,
    list_fixture_calendars,
)
from m365_mcp.apps.outlook.mock_ui import OutlookMockFixture
from m365_mcp.apps.outlook.readiness import OutlookReadinessReport

_MAX_EVENTS = 500
_MAX_PAGE_SIZE = 100
_MAX_QUERY_LENGTH = 200
_MIN_DAY_OFFSET = -3650
_MAX_DAY_OFFSET = 3650
_MINUTES_PER_DAY = 1440
_MAX_DURATION_MINUTES = 60 * 24 * 30


class EventShowAs(StrEnum):
    """Closed availability presentation states for a synthetic event."""

    FREE = "FREE"
    TENTATIVE = "TENTATIVE"
    BUSY = "BUSY"
    OUT_OF_OFFICE = "OUT_OF_OFFICE"


class EventSensitivity(StrEnum):
    """Closed sensitivity classification for a synthetic event."""

    NORMAL = "NORMAL"
    PRIVATE = "PRIVATE"


@dataclass(frozen=True)
class SyntheticEvent:
    """Tenant-neutral calendar event bound to one synthetic calendar."""

    event_key: str
    calendar_key: str
    subject: str
    start_day_offset: int
    start_minute_of_day: int
    duration_minutes: int
    is_all_day: bool = False
    is_cancelled: bool = False
    is_recurring_instance: bool = False
    show_as: EventShowAs = EventShowAs.BUSY
    sensitivity: EventSensitivity = EventSensitivity.NORMAL

    def __post_init__(self) -> None:
        for field_name in ("event_key", "calendar_key"):
            value = getattr(self, field_name)
            invalid = (
                not value
                or value != value.strip()
                or any(char.isspace() for char in value)
            )
            if invalid:
                raise ValueError(f"{field_name} must be a non-empty semantic token")
        if not self.subject or self.subject != self.subject.strip():
            raise ValueError("subject must be non-empty")
        for field_name in ("is_all_day", "is_cancelled", "is_recurring_instance"):
            if not isinstance(getattr(self, field_name), bool):
                raise ValueError(f"{field_name} must be a boolean")
        if not isinstance(self.show_as, EventShowAs):
            raise ValueError("show_as must be a closed EventShowAs")
        if not isinstance(self.sensitivity, EventSensitivity):
            raise ValueError("sensitivity must be a closed EventSensitivity")

        for field_name in ("start_day_offset", "start_minute_of_day", "duration_minutes"):
            value = getattr(self, field_name)
            if not isinstance(value, int) or isinstance(value, bool):
                raise ValueError(f"{field_name} must be an integer")

        if not _MIN_DAY_OFFSET <= self.start_day_offset <= _MAX_DAY_OFFSET:
            raise ValueError("start_day_offset exceeds the bounded day-offset window")
        if not 0 <= self.start_minute_of_day < _MINUTES_PER_DAY:
            raise ValueError("start_minute_of_day must fall inside a single day")
        if not 1 <= self.duration_minutes <= _MAX_DURATION_MINUTES:
            raise ValueError("duration_minutes exceeds the bounded duration window")

        if self.is_all_day:
            if self.start_minute_of_day != 0:
                raise ValueError("an all-day event must start at minute zero")
            if self.duration_minutes % _MINUTES_PER_DAY != 0:
                raise ValueError("an all-day event must span whole days")


@dataclass(frozen=True)
class EventProjection:
    """Bounded read-only event projection with derived relative end position."""

    event_key: str
    calendar_key: str
    subject: str
    start_day_offset: int
    start_minute_of_day: int
    duration_minutes: int
    end_day_offset: int
    end_minute_of_day: int
    is_all_day: bool
    is_cancelled: bool
    is_recurring_instance: bool
    show_as: EventShowAs
    sensitivity: EventSensitivity
    synthetic: bool

    def to_projection(self) -> dict[str, object]:
        return {
            "event_key": self.event_key,
            "calendar_key": self.calendar_key,
            "subject": self.subject,
            "start_day_offset": self.start_day_offset,
            "start_minute_of_day": self.start_minute_of_day,
            "duration_minutes": self.duration_minutes,
            "end_day_offset": self.end_day_offset,
            "end_minute_of_day": self.end_minute_of_day,
            "is_all_day": self.is_all_day,
            "is_cancelled": self.is_cancelled,
            "is_recurring_instance": self.is_recurring_instance,
            "show_as": self.show_as.value,
            "sensitivity": self.sensitivity.value,
            "synthetic": self.synthetic,
        }


@dataclass(frozen=True)
class EventSearchRequest:
    """Closed bounded search request over synthetic event metadata."""

    query: str | None = None
    calendar_key: str | None = None
    show_as: EventShowAs | None = None
    include_cancelled: bool = False
    from_day_offset: int | None = None
    to_day_offset: int | None = None
    offset: int = 0
    limit: int = 50

    def __post_init__(self) -> None:
        if self.query is not None:
            normalized = self.query.strip()
            if not normalized:
                raise ValueError("query must not be empty when supplied")
            if len(normalized) > _MAX_QUERY_LENGTH:
                raise ValueError(f"query must be at most {_MAX_QUERY_LENGTH} characters")
        if self.calendar_key is not None:
            invalid = (
                not self.calendar_key
                or self.calendar_key != self.calendar_key.strip()
                or any(char.isspace() for char in self.calendar_key)
            )
            if invalid:
                raise ValueError("calendar_key must be a non-empty semantic token")
        if self.show_as is not None and not isinstance(self.show_as, EventShowAs):
            raise ValueError("show_as must be a closed EventShowAs")
        if not isinstance(self.include_cancelled, bool):
            raise ValueError("include_cancelled must be a boolean")
        for field_name in ("from_day_offset", "to_day_offset"):
            value = getattr(self, field_name)
            if value is None:
                continue
            if not isinstance(value, int) or isinstance(value, bool):
                raise ValueError(f"{field_name} must be an integer day offset")
            if not _MIN_DAY_OFFSET <= value <= _MAX_DAY_OFFSET:
                raise ValueError(f"{field_name} exceeds the bounded day-offset window")
        if (
            self.from_day_offset is not None
            and self.to_day_offset is not None
            and self.from_day_offset > self.to_day_offset
        ):
            raise ValueError("from_day_offset must not exceed to_day_offset")
        if self.offset < 0:
            raise ValueError("offset must be non-negative")
        if not 1 <= self.limit <= _MAX_PAGE_SIZE:
            raise ValueError(f"limit must be between 1 and {_MAX_PAGE_SIZE}")


@dataclass(frozen=True)
class EventSearchResult:
    """Deterministic synthetic event result page."""

    items: tuple[EventProjection, ...]
    offset: int
    limit: int
    total_matching: int
    has_more: bool
    synthetic: bool


def default_synthetic_events() -> tuple[SyntheticEvent, ...]:
    """Return the explicit synthetic event catalog."""
    return (
        SyntheticEvent(
            event_key="evt-001",
            calendar_key="cal-primary",
            subject="Synthetic planning session",
            start_day_offset=0,
            start_minute_of_day=540,
            duration_minutes=60,
        ),
        SyntheticEvent(
            event_key="evt-002",
            calendar_key="cal-primary",
            subject="Synthetic focus block",
            start_day_offset=1,
            start_minute_of_day=0,
            duration_minutes=_MINUTES_PER_DAY,
            is_all_day=True,
            show_as=EventShowAs.OUT_OF_OFFICE,
        ),
        SyntheticEvent(
            event_key="evt-003",
            calendar_key="cal-team",
            subject="Synthetic team sync",
            start_day_offset=2,
            start_minute_of_day=600,
            duration_minutes=30,
            is_recurring_instance=True,
            show_as=EventShowAs.TENTATIVE,
        ),
        SyntheticEvent(
            event_key="evt-004",
            calendar_key="cal-team",
            subject="Synthetic cancelled review",
            start_day_offset=3,
            start_minute_of_day=660,
            duration_minutes=45,
            is_cancelled=True,
            show_as=EventShowAs.FREE,
        ),
    )


def _validate(
    events: tuple[SyntheticEvent, ...],
    calendars: tuple[SyntheticCalendar, ...],
) -> None:
    if len(events) > _MAX_EVENTS:
        raise ValueError("event catalog exceeds bounded size")

    keys = tuple(event.event_key for event in events)
    if len(set(keys)) != len(keys):
        raise ValueError("event catalog keys must be unique per event_key")

    known = {calendar.calendar_key for calendar in calendars}
    for event in events:
        if event.calendar_key not in known:
            raise ValueError("event references unknown synthetic calendar_key")


def _project(event: SyntheticEvent) -> EventProjection:
    absolute_end = event.start_minute_of_day + event.duration_minutes
    return EventProjection(
        event_key=event.event_key,
        calendar_key=event.calendar_key,
        subject=event.subject,
        start_day_offset=event.start_day_offset,
        start_minute_of_day=event.start_minute_of_day,
        duration_minutes=event.duration_minutes,
        end_day_offset=event.start_day_offset + absolute_end // _MINUTES_PER_DAY,
        end_minute_of_day=absolute_end % _MINUTES_PER_DAY,
        is_all_day=event.is_all_day,
        is_cancelled=event.is_cancelled,
        is_recurring_instance=event.is_recurring_instance,
        show_as=event.show_as,
        sensitivity=event.sensitivity,
        synthetic=True,
    )


def _prepare(
    fixture: OutlookMockFixture,
    readiness: OutlookReadinessReport,
    events: tuple[SyntheticEvent, ...] | None,
    calendars: tuple[SyntheticCalendar, ...] | None,
) -> tuple[SyntheticEvent, ...]:
    if not fixture.synthetic:
        raise ValueError("OUT-021 fixture execution requires synthetic=true")
    if not readiness.ready_for_readonly_discovery:
        raise ValueError("Outlook read-only discovery is not ready")

    calendar_catalog = default_synthetic_calendars() if calendars is None else calendars
    # Reuse the OUT-020 gate so an invalid calendar catalog cannot be bypassed here.
    list_fixture_calendars(fixture, readiness=readiness, calendars=calendar_catalog)

    catalog = default_synthetic_events() if events is None else events
    _validate(catalog, calendar_catalog)
    return catalog


def search_fixture_events(
    fixture: OutlookMockFixture,
    request: EventSearchRequest,
    *,
    readiness: OutlookReadinessReport,
    events: tuple[SyntheticEvent, ...] | None = None,
    calendars: tuple[SyntheticCalendar, ...] | None = None,
) -> EventSearchResult:
    """Search bounded synthetic event metadata when read discovery is ready."""
    catalog = _prepare(fixture, readiness, events, calendars)

    if request.calendar_key is not None:
        calendar_catalog = default_synthetic_calendars() if calendars is None else calendars
        if request.calendar_key not in {item.calendar_key for item in calendar_catalog}:
            raise ValueError("unknown synthetic calendar_key")

    query = request.query.strip().casefold() if request.query is not None else None
    matching = tuple(
        event
        for event in catalog
        if (query is None or query in event.subject.casefold())
        and (request.calendar_key is None or event.calendar_key == request.calendar_key)
        and (request.show_as is None or event.show_as is request.show_as)
        and (request.include_cancelled or not event.is_cancelled)
        and (
            request.from_day_offset is None
            or event.start_day_offset >= request.from_day_offset
        )
        and (
            request.to_day_offset is None
            or event.start_day_offset <= request.to_day_offset
        )
    )
    ordered = tuple(
        sorted(
            matching,
            key=lambda event: (
                event.start_day_offset,
                event.start_minute_of_day,
                event.event_key,
            ),
        )
    )
    page = ordered[request.offset : request.offset + request.limit]
    return EventSearchResult(
        items=tuple(_project(event) for event in page),
        offset=request.offset,
        limit=request.limit,
        total_matching=len(ordered),
        has_more=request.offset + len(page) < len(ordered),
        synthetic=True,
    )


def list_fixture_events(
    fixture: OutlookMockFixture,
    *,
    readiness: OutlookReadinessReport,
    calendar_key: str | None = None,
    events: tuple[SyntheticEvent, ...] | None = None,
    calendars: tuple[SyntheticCalendar, ...] | None = None,
) -> EventSearchResult:
    """List bounded synthetic events, optionally scoped to one calendar."""
    return search_fixture_events(
        fixture,
        EventSearchRequest(calendar_key=calendar_key, limit=_MAX_PAGE_SIZE),
        readiness=readiness,
        events=events,
        calendars=calendars,
    )


def get_fixture_event(
    fixture: OutlookMockFixture,
    event_key: str,
    *,
    readiness: OutlookReadinessReport,
    events: tuple[SyntheticEvent, ...] | None = None,
    calendars: tuple[SyntheticCalendar, ...] | None = None,
) -> EventProjection:
    """Read one existing synthetic event, failing closed otherwise."""
    if not event_key or event_key != event_key.strip():
        raise ValueError("event_key must be a non-empty semantic token")

    catalog = _prepare(fixture, readiness, events, calendars)
    match = next((event for event in catalog if event.event_key == event_key), None)
    if match is None:
        raise ValueError("synthetic event_key not found")
    return _project(match)


__all__ = [
    "EventProjection",
    "EventSearchRequest",
    "EventSearchResult",
    "EventSensitivity",
    "EventShowAs",
    "SyntheticEvent",
    "default_synthetic_events",
    "get_fixture_event",
    "list_fixture_events",
    "search_fixture_events",
]
