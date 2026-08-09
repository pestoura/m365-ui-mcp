"""Synthetic-only Outlook working context settings for OUT-098.

The model represents working hours, a tenant-neutral time-zone key and a coarse
work-location kind. It never stores a physical address, URL, selector, session
material, token or live Microsoft 365 evidence.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from m365_mcp.apps.outlook.mock_ui import OutlookMockFixture
from m365_mcp.apps.outlook.readiness import OutlookReadinessReport

_MAX_TIME_ZONE_KEY = 64


class WorkLocationKind(StrEnum):
    """Closed coarse work-location kinds with no physical location data."""

    UNSPECIFIED = "UNSPECIFIED"
    OFFICE = "OFFICE"
    REMOTE = "REMOTE"
    HYBRID = "HYBRID"


def _validate_time_zone_key(value: str) -> None:
    if (
        not value
        or value != value.strip()
        or len(value) > _MAX_TIME_ZONE_KEY
        or any(char.isspace() for char in value)
        or "@" in value
        or "://" in value
    ):
        raise ValueError("time_zone_key must be a bounded semantic key")


@dataclass(frozen=True)
class WorkingHours:
    """Relative weekly working-hours policy."""

    weekdays: tuple[int, ...]
    start_minute_of_day: int
    end_minute_of_day: int

    def __post_init__(self) -> None:
        if not self.weekdays or len(set(self.weekdays)) != len(self.weekdays):
            raise ValueError("weekdays must be non-empty and unique")
        if any(day < 0 or day > 6 for day in self.weekdays):
            raise ValueError("weekdays must be bounded to 0..6")
        if not 0 <= self.start_minute_of_day < self.end_minute_of_day <= 1440:
            raise ValueError("working hours must form a bounded positive interval")

    def to_projection(self) -> dict[str, object]:
        return {
            "weekdays": list(self.weekdays),
            "start_minute_of_day": self.start_minute_of_day,
            "end_minute_of_day": self.end_minute_of_day,
        }


@dataclass(frozen=True)
class WorkingContextSettings:
    """One synthetic working-context state."""

    time_zone_key: str
    working_hours: WorkingHours
    work_location: WorkLocationKind

    def __post_init__(self) -> None:
        _validate_time_zone_key(self.time_zone_key)
        if not isinstance(self.working_hours, WorkingHours):
            raise ValueError("working_hours must be WorkingHours")
        if not isinstance(self.work_location, WorkLocationKind):
            raise ValueError("work_location must be a closed WorkLocationKind")

    def to_projection(self) -> dict[str, object]:
        return {
            "time_zone_key": self.time_zone_key,
            "working_hours": self.working_hours.to_projection(),
            "work_location": self.work_location.value,
            "synthetic": True,
        }


@dataclass(frozen=True)
class WorkingContextMutationResult:
    """Read-back proof for a synthetic settings replacement."""

    previous: WorkingContextSettings
    read_back: WorkingContextSettings
    changed: bool
    verified: bool
    synthetic: bool


def default_working_context_settings() -> WorkingContextSettings:
    """Return a deterministic tenant-neutral default."""
    return WorkingContextSettings(
        time_zone_key="EUROPE_WEST",
        working_hours=WorkingHours((0, 1, 2, 3, 4), 540, 1020),
        work_location=WorkLocationKind.UNSPECIFIED,
    )


def _gate(fixture: OutlookMockFixture, readiness: OutlookReadinessReport) -> None:
    if not fixture.synthetic:
        raise ValueError("OUT-098 fixture execution requires synthetic=true")
    if not readiness.ready_for_readonly_discovery:
        raise ValueError("Outlook read-only discovery is not ready")


def read_working_context_settings(
    fixture: OutlookMockFixture,
    *,
    readiness: OutlookReadinessReport,
    settings: WorkingContextSettings | None = None,
) -> WorkingContextSettings:
    """Read deterministic synthetic working-context state."""
    _gate(fixture, readiness)
    return default_working_context_settings() if settings is None else settings


def apply_working_context_settings(
    fixture: OutlookMockFixture,
    desired: WorkingContextSettings,
    *,
    readiness: OutlookReadinessReport,
    settings: WorkingContextSettings | None = None,
) -> tuple[WorkingContextSettings, WorkingContextMutationResult]:
    """Replace synthetic settings and prove exact state by read-back."""
    _gate(fixture, readiness)
    if not isinstance(desired, WorkingContextSettings):
        raise ValueError("desired must be WorkingContextSettings")
    previous = read_working_context_settings(
        fixture,
        readiness=readiness,
        settings=settings,
    )
    updated = desired
    read_back = read_working_context_settings(
        fixture,
        readiness=readiness,
        settings=updated,
    )
    if read_back != desired:
        raise RuntimeError("working-context read-back did not prove requested state")
    return updated, WorkingContextMutationResult(
        previous=previous,
        read_back=read_back,
        changed=previous != updated,
        verified=True,
        synthetic=True,
    )


__all__ = [
    "WorkLocationKind",
    "WorkingContextMutationResult",
    "WorkingContextSettings",
    "WorkingHours",
    "apply_working_context_settings",
    "default_working_context_settings",
    "read_working_context_settings",
]
