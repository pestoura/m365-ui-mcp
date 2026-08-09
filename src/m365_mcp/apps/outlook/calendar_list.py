"""Synthetic-only Outlook calendar listing for OUT-020.

The model exposes a bounded, tenant-neutral catalog of calendars available to
the synthetic Outlook fixture. It carries no mailbox/account/tenant identity,
URL, selector, XPath, JavaScript, browser primitive or absolute timestamp, and
it claims no live Outlook calendar support. Calendar events are out of scope
and arrive with OUT-021.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from m365_mcp.apps.outlook.mock_ui import OutlookMockFixture
from m365_mcp.apps.outlook.readiness import OutlookReadinessReport

_MAX_CALENDARS = 100


class CalendarKind(StrEnum):
    """Closed calendar kinds for read-only listing semantics."""

    PRIMARY = "PRIMARY"
    SECONDARY = "SECONDARY"
    GROUP = "GROUP"
    BIRTHDAY = "BIRTHDAY"


class CalendarColorToken(StrEnum):
    """Closed semantic colour tokens, never raw UI colour values."""

    BLUE = "BLUE"
    GREEN = "GREEN"
    ORANGE = "ORANGE"
    PURPLE = "PURPLE"


@dataclass(frozen=True)
class SyntheticCalendar:
    """Tenant-neutral calendar definition bound to the synthetic fixture."""

    calendar_key: str
    display_name: str
    kind: CalendarKind = CalendarKind.SECONDARY
    color_token: CalendarColorToken = CalendarColorToken.BLUE
    is_default_view: bool = False
    can_read: bool = True

    def __post_init__(self) -> None:
        invalid_key = (
            not self.calendar_key
            or self.calendar_key != self.calendar_key.strip()
            or any(char.isspace() for char in self.calendar_key)
        )
        if invalid_key:
            raise ValueError("calendar_key must be a non-empty semantic token")
        if not self.display_name or self.display_name != self.display_name.strip():
            raise ValueError("display_name must be non-empty")
        if not isinstance(self.kind, CalendarKind):
            raise ValueError("kind must be a closed CalendarKind")
        if not isinstance(self.color_token, CalendarColorToken):
            raise ValueError("color_token must be a closed CalendarColorToken")
        if not isinstance(self.is_default_view, bool):
            raise ValueError("is_default_view must be a boolean")
        if not isinstance(self.can_read, bool):
            raise ValueError("can_read must be a boolean")
        if self.is_default_view and not self.can_read:
            raise ValueError("a default-view calendar must be readable")


@dataclass(frozen=True)
class CalendarNode:
    """Bounded read-only calendar projection."""

    calendar_key: str
    display_name: str
    kind: CalendarKind
    color_token: CalendarColorToken
    is_default_view: bool
    can_read: bool
    synthetic: bool

    def to_projection(self) -> dict[str, object]:
        return {
            "calendar_key": self.calendar_key,
            "display_name": self.display_name,
            "kind": self.kind.value,
            "color_token": self.color_token.value,
            "is_default_view": self.is_default_view,
            "can_read": self.can_read,
            "synthetic": self.synthetic,
        }


@dataclass(frozen=True)
class CalendarListResult:
    """Deterministic bounded calendar listing for one synthetic fixture."""

    calendars: tuple[CalendarNode, ...]
    calendar_count: int
    readable_count: int
    default_calendar_key: str
    synthetic: bool


def default_synthetic_calendars() -> tuple[SyntheticCalendar, ...]:
    """Return the explicit synthetic calendar catalog."""
    return (
        SyntheticCalendar(
            calendar_key="cal-primary",
            display_name="Synthetic Calendar",
            kind=CalendarKind.PRIMARY,
            color_token=CalendarColorToken.BLUE,
            is_default_view=True,
        ),
        SyntheticCalendar(
            calendar_key="cal-team",
            display_name="Synthetic Team Calendar",
            kind=CalendarKind.GROUP,
            color_token=CalendarColorToken.GREEN,
        ),
    )


def _validate(catalog: tuple[SyntheticCalendar, ...]) -> None:
    if not catalog:
        raise ValueError("calendar catalog must not be empty")
    if len(catalog) > _MAX_CALENDARS:
        raise ValueError("calendar catalog exceeds bounded size")

    keys = tuple(calendar.calendar_key for calendar in catalog)
    if len(set(keys)) != len(keys):
        raise ValueError("calendar catalog keys must be unique per calendar_key")

    primaries = tuple(item for item in catalog if item.kind is CalendarKind.PRIMARY)
    if len(primaries) != 1:
        raise ValueError("calendar catalog requires exactly one PRIMARY calendar")

    defaults = tuple(item for item in catalog if item.is_default_view)
    if len(defaults) != 1:
        raise ValueError("calendar catalog requires exactly one default-view calendar")


def _project(calendar: SyntheticCalendar) -> CalendarNode:
    return CalendarNode(
        calendar_key=calendar.calendar_key,
        display_name=calendar.display_name,
        kind=calendar.kind,
        color_token=calendar.color_token,
        is_default_view=calendar.is_default_view,
        can_read=calendar.can_read,
        synthetic=True,
    )


def list_fixture_calendars(
    fixture: OutlookMockFixture,
    *,
    readiness: OutlookReadinessReport,
    calendars: tuple[SyntheticCalendar, ...] | None = None,
) -> CalendarListResult:
    """List the bounded synthetic calendar catalog when read discovery is ready."""
    if not fixture.synthetic:
        raise ValueError("OUT-020 fixture execution requires synthetic=true")
    if not readiness.ready_for_readonly_discovery:
        raise ValueError("Outlook read-only discovery is not ready")

    catalog = default_synthetic_calendars() if calendars is None else calendars
    _validate(catalog)

    nodes = tuple(_project(calendar) for calendar in catalog)
    default_node = next(node for node in nodes if node.is_default_view)
    return CalendarListResult(
        calendars=nodes,
        calendar_count=len(nodes),
        readable_count=sum(1 for node in nodes if node.can_read),
        default_calendar_key=default_node.calendar_key,
        synthetic=True,
    )


def read_fixture_calendar(
    fixture: OutlookMockFixture,
    calendar_key: str,
    *,
    readiness: OutlookReadinessReport,
    calendars: tuple[SyntheticCalendar, ...] | None = None,
) -> CalendarNode:
    """Read one existing synthetic calendar entry, failing closed otherwise."""
    if not calendar_key or calendar_key != calendar_key.strip():
        raise ValueError("calendar_key must be a non-empty semantic token")
    if not fixture.synthetic:
        raise ValueError("OUT-020 fixture execution requires synthetic=true")
    if not readiness.ready_for_readonly_discovery:
        raise ValueError("Outlook read-only discovery is not ready")

    catalog = default_synthetic_calendars() if calendars is None else calendars
    _validate(catalog)

    match = next(
        (calendar for calendar in catalog if calendar.calendar_key == calendar_key),
        None,
    )
    if match is None:
        raise ValueError("synthetic calendar_key not found")
    return _project(match)


__all__ = [
    "CalendarColorToken",
    "CalendarKind",
    "CalendarListResult",
    "CalendarNode",
    "SyntheticCalendar",
    "default_synthetic_calendars",
    "list_fixture_calendars",
    "read_fixture_calendar",
]
