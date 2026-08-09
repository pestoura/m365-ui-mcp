"""Synthetic-only Outlook shared-calendar reads for OUT-024.

A shared calendar is a synthetic calendar reached through a delegated scope
rather than the owner's own mailbox. This module models the delegated
permission level and enforces it over the OUT-020..OUT-022 read surface, so a
shared calendar can never project more than its granted level allows.

Delegation is expressed with opaque scope keys only. No mailbox address,
delegate identity, directory record, sharing invitation, share URL or tenant is
modelled, and no live sharing lookup is performed.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import StrEnum

from m365_mcp.apps.outlook.availability_reads import (
    AvailabilityResult,
    AvailabilityWindow,
    read_fixture_availability,
)
from m365_mcp.apps.outlook.calendar_events import (
    EventSearchResult,
    SyntheticEvent,
    list_fixture_events,
)
from m365_mcp.apps.outlook.calendar_list import SyntheticCalendar
from m365_mcp.apps.outlook.mock_ui import OutlookMockFixture
from m365_mcp.apps.outlook.readiness import OutlookReadinessReport

_MAX_SHARED_SCOPES = 50


class SharedCalendarPermission(StrEnum):
    """Closed delegated permission levels, ordered least to most permissive."""

    NONE = "NONE"
    FREE_BUSY_ONLY = "FREE_BUSY_ONLY"
    LIMITED_DETAILS = "LIMITED_DETAILS"
    FULL_DETAILS = "FULL_DETAILS"


_PERMISSION_RANK: dict[SharedCalendarPermission, int] = {
    SharedCalendarPermission.NONE: 0,
    SharedCalendarPermission.FREE_BUSY_ONLY: 1,
    SharedCalendarPermission.LIMITED_DETAILS: 2,
    SharedCalendarPermission.FULL_DETAILS: 3,
}

_REDACTED_SUBJECT = "REDACTED_BY_SHARED_CALENDAR_PERMISSION"


@dataclass(frozen=True)
class SharedCalendarScope:
    """Tenant-neutral delegated scope over one synthetic calendar."""

    scope_key: str
    calendar_key: str
    permission: SharedCalendarPermission = SharedCalendarPermission.FREE_BUSY_ONLY

    def __post_init__(self) -> None:
        for field_name in ("scope_key", "calendar_key"):
            value = getattr(self, field_name)
            invalid = (
                not value
                or value != value.strip()
                or any(char.isspace() for char in value)
            )
            if invalid:
                raise ValueError(f"{field_name} must be a non-empty semantic token")
        if "@" in self.scope_key:
            raise ValueError("scope_key must not encode an address identity")
        if not isinstance(self.permission, SharedCalendarPermission):
            raise ValueError("permission must be a closed SharedCalendarPermission")


@dataclass(frozen=True)
class SharedCalendarReadState:
    """What a delegated scope is structurally allowed to read."""

    scope_key: str
    calendar_key: str
    permission: SharedCalendarPermission
    may_read_availability: bool
    may_read_events: bool
    may_read_subjects: bool
    synthetic: bool

    def to_projection(self) -> dict[str, object]:
        return {
            "scope_key": self.scope_key,
            "calendar_key": self.calendar_key,
            "permission": self.permission.value,
            "may_read_availability": self.may_read_availability,
            "may_read_events": self.may_read_events,
            "may_read_subjects": self.may_read_subjects,
            "synthetic": self.synthetic,
        }


def default_synthetic_shared_scopes() -> tuple[SharedCalendarScope, ...]:
    """Return the explicit synthetic shared-calendar scope catalog."""
    return (
        SharedCalendarScope(
            scope_key="scope-team-freebusy",
            calendar_key="cal-team",
            permission=SharedCalendarPermission.FREE_BUSY_ONLY,
        ),
        SharedCalendarScope(
            scope_key="scope-team-limited",
            calendar_key="cal-team",
            permission=SharedCalendarPermission.LIMITED_DETAILS,
        ),
    )


def _validate(scopes: tuple[SharedCalendarScope, ...]) -> None:
    if not scopes:
        raise ValueError("shared calendar scope catalog must not be empty")
    if len(scopes) > _MAX_SHARED_SCOPES:
        raise ValueError("shared calendar scope catalog exceeds bounded size")

    keys = tuple(scope.scope_key for scope in scopes)
    if len(set(keys)) != len(keys):
        raise ValueError("shared calendar scopes must be unique per scope_key")


def _resolve(
    scope_key: str,
    scopes: tuple[SharedCalendarScope, ...] | None,
) -> SharedCalendarScope:
    if not scope_key or scope_key != scope_key.strip():
        raise ValueError("scope_key must be a non-empty semantic token")
    catalog = default_synthetic_shared_scopes() if scopes is None else scopes
    _validate(catalog)
    match = next((item for item in catalog if item.scope_key == scope_key), None)
    if match is None:
        raise ValueError("synthetic scope_key not found")
    return match


def _allows(scope: SharedCalendarScope, minimum: SharedCalendarPermission) -> bool:
    return _PERMISSION_RANK[scope.permission] >= _PERMISSION_RANK[minimum]


def read_shared_calendar_state(
    fixture: OutlookMockFixture,
    scope_key: str,
    *,
    readiness: OutlookReadinessReport,
    scopes: tuple[SharedCalendarScope, ...] | None = None,
) -> SharedCalendarReadState:
    """Project what one delegated scope may read, without reading anything yet."""
    if not fixture.synthetic:
        raise ValueError("OUT-024 fixture execution requires synthetic=true")
    if not readiness.ready_for_readonly_discovery:
        raise ValueError("Outlook read-only discovery is not ready")

    scope = _resolve(scope_key, scopes)
    return SharedCalendarReadState(
        scope_key=scope.scope_key,
        calendar_key=scope.calendar_key,
        permission=scope.permission,
        may_read_availability=_allows(scope, SharedCalendarPermission.FREE_BUSY_ONLY),
        may_read_events=_allows(scope, SharedCalendarPermission.LIMITED_DETAILS),
        may_read_subjects=_allows(scope, SharedCalendarPermission.FULL_DETAILS),
        synthetic=True,
    )


def read_shared_calendar_availability(
    fixture: OutlookMockFixture,
    scope_key: str,
    window: AvailabilityWindow,
    *,
    readiness: OutlookReadinessReport,
    scopes: tuple[SharedCalendarScope, ...] | None = None,
    events: tuple[SyntheticEvent, ...] | None = None,
    calendars: tuple[SyntheticCalendar, ...] | None = None,
) -> AvailabilityResult:
    """Read delegated free-busy, requiring at least FREE_BUSY_ONLY."""
    state = read_shared_calendar_state(
        fixture,
        scope_key,
        readiness=readiness,
        scopes=scopes,
    )
    if not state.may_read_availability:
        raise ValueError("shared calendar permission does not allow availability reads")

    return read_fixture_availability(
        fixture,
        window,
        readiness=readiness,
        calendar_key=state.calendar_key,
        events=events,
        calendars=calendars,
    )


def list_shared_calendar_events(
    fixture: OutlookMockFixture,
    scope_key: str,
    *,
    readiness: OutlookReadinessReport,
    scopes: tuple[SharedCalendarScope, ...] | None = None,
    events: tuple[SyntheticEvent, ...] | None = None,
    calendars: tuple[SyntheticCalendar, ...] | None = None,
) -> EventSearchResult:
    """List delegated events, redacting subjects below FULL_DETAILS."""
    state = read_shared_calendar_state(
        fixture,
        scope_key,
        readiness=readiness,
        scopes=scopes,
    )
    if not state.may_read_events:
        raise ValueError("shared calendar permission does not allow event reads")

    listing = list_fixture_events(
        fixture,
        readiness=readiness,
        calendar_key=state.calendar_key,
        events=events,
        calendars=calendars,
    )
    if state.may_read_subjects:
        return listing

    redacted = tuple(
        replace(item, subject=_REDACTED_SUBJECT) for item in listing.items
    )
    return EventSearchResult(
        items=redacted,
        offset=listing.offset,
        limit=listing.limit,
        total_matching=listing.total_matching,
        has_more=listing.has_more,
        synthetic=True,
    )


__all__ = [
    "SharedCalendarPermission",
    "SharedCalendarReadState",
    "SharedCalendarScope",
    "default_synthetic_shared_scopes",
    "list_shared_calendar_events",
    "read_shared_calendar_availability",
    "read_shared_calendar_state",
]
