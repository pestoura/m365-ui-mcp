"""Synthetic-only Outlook Scheduling Assistant structural reads for OUT-023.

The Scheduling Assistant surface is modelled *structurally*: it composes the
OUT-022 availability grid for a bounded set of synthetic participants and
reports where their relative free-busy grids overlap. It is not a meeting
booking, invitation, attendee-lookup or directory-resolution capability, and it
performs no live scheduling query.

Participants are opaque synthetic keys. No attendee address, display identity,
directory record, mailbox or tenant is modelled, and each participant's
calendar scope must resolve inside the synthetic OUT-020 catalog.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from m365_mcp.apps.outlook.availability_reads import (
    AvailabilityState,
    AvailabilityWindow,
    read_fixture_availability,
)
from m365_mcp.apps.outlook.calendar_events import SyntheticEvent
from m365_mcp.apps.outlook.calendar_list import SyntheticCalendar
from m365_mcp.apps.outlook.mock_ui import OutlookMockFixture
from m365_mcp.apps.outlook.readiness import OutlookReadinessReport

_MAX_PARTICIPANTS = 50


class ParticipantRole(StrEnum):
    """Closed structural participant roles for grid composition."""

    ORGANIZER = "ORGANIZER"
    REQUIRED = "REQUIRED"
    OPTIONAL = "OPTIONAL"


class SlotFeasibility(StrEnum):
    """Closed feasibility classification for one composed grid column."""

    ALL_FREE = "ALL_FREE"
    REQUIRED_FREE = "REQUIRED_FREE"
    CONFLICTED = "CONFLICTED"


@dataclass(frozen=True)
class SyntheticParticipant:
    """Tenant-neutral scheduling participant bound to a synthetic calendar."""

    participant_key: str
    role: ParticipantRole = ParticipantRole.REQUIRED
    calendar_key: str | None = None

    def __post_init__(self) -> None:
        for field_name in ("participant_key", "calendar_key"):
            value = getattr(self, field_name)
            if value is None:
                continue
            invalid = (
                not value
                or value != value.strip()
                or any(char.isspace() for char in value)
            )
            if invalid:
                raise ValueError(f"{field_name} must be a non-empty semantic token")
        if "@" in self.participant_key:
            raise ValueError("participant_key must not encode an address identity")
        if not isinstance(self.role, ParticipantRole):
            raise ValueError("role must be a closed ParticipantRole")


@dataclass(frozen=True)
class ParticipantGridRow:
    """One participant's relative availability row inside the composed grid."""

    participant_key: str
    role: ParticipantRole
    calendar_key: str | None
    states: tuple[AvailabilityState, ...]
    busy_slot_count: int
    synthetic: bool

    def to_projection(self) -> dict[str, object]:
        return {
            "participant_key": self.participant_key,
            "role": self.role.value,
            "calendar_key": self.calendar_key,
            "states": [state.value for state in self.states],
            "busy_slot_count": self.busy_slot_count,
            "synthetic": self.synthetic,
        }


@dataclass(frozen=True)
class SchedulingSlot:
    """One composed grid column with structural feasibility only."""

    day_offset: int
    start_minute_of_day: int
    end_minute_of_day: int
    feasibility: SlotFeasibility
    free_participant_count: int
    conflicted_participant_count: int
    synthetic: bool

    def to_projection(self) -> dict[str, object]:
        return {
            "day_offset": self.day_offset,
            "start_minute_of_day": self.start_minute_of_day,
            "end_minute_of_day": self.end_minute_of_day,
            "feasibility": self.feasibility.value,
            "free_participant_count": self.free_participant_count,
            "conflicted_participant_count": self.conflicted_participant_count,
            "synthetic": self.synthetic,
        }


@dataclass(frozen=True)
class SchedulingGrid:
    """Deterministic Scheduling Assistant structural projection."""

    rows: tuple[ParticipantGridRow, ...]
    slots: tuple[SchedulingSlot, ...]
    participant_count: int
    slot_count: int
    all_free_slot_count: int
    required_free_slot_count: int
    synthetic: bool


def default_synthetic_participants() -> tuple[SyntheticParticipant, ...]:
    """Return the explicit synthetic participant catalog."""
    return (
        SyntheticParticipant(
            participant_key="participant-organizer",
            role=ParticipantRole.ORGANIZER,
            calendar_key="cal-primary",
        ),
        SyntheticParticipant(
            participant_key="participant-required",
            role=ParticipantRole.REQUIRED,
            calendar_key="cal-team",
        ),
    )


def _validate(participants: tuple[SyntheticParticipant, ...]) -> None:
    if not participants:
        raise ValueError("participant catalog must not be empty")
    if len(participants) > _MAX_PARTICIPANTS:
        raise ValueError("participant catalog exceeds bounded size")

    keys = tuple(item.participant_key for item in participants)
    if len(set(keys)) != len(keys):
        raise ValueError("participant catalog keys must be unique per participant_key")

    organizers = tuple(
        item for item in participants if item.role is ParticipantRole.ORGANIZER
    )
    if len(organizers) != 1:
        raise ValueError("participant catalog requires exactly one ORGANIZER")


def read_fixture_scheduling_grid(
    fixture: OutlookMockFixture,
    window: AvailabilityWindow,
    *,
    readiness: OutlookReadinessReport,
    participants: tuple[SyntheticParticipant, ...] | None = None,
    events: tuple[SyntheticEvent, ...] | None = None,
    calendars: tuple[SyntheticCalendar, ...] | None = None,
) -> SchedulingGrid:
    """Compose a bounded structural Scheduling Assistant grid, failing closed."""
    if not isinstance(window, AvailabilityWindow):
        raise ValueError("window must be a bounded AvailabilityWindow")

    catalog = default_synthetic_participants() if participants is None else participants
    _validate(catalog)

    rows: list[ParticipantGridRow] = []
    columns: list[tuple[int, int, int]] = []
    for participant in catalog:
        # OUT-022 re-executes the OUT-021 event gate, the OUT-020 calendar gate
        # and the OUT-007 readiness/synthetic gates for every participant scope.
        availability = read_fixture_availability(
            fixture,
            window,
            readiness=readiness,
            calendar_key=participant.calendar_key,
            events=events,
            calendars=calendars,
        )
        if not columns:
            columns = [
                (slot.day_offset, slot.start_minute_of_day, slot.end_minute_of_day)
                for slot in availability.slots
            ]
        rows.append(
            ParticipantGridRow(
                participant_key=participant.participant_key,
                role=participant.role,
                calendar_key=participant.calendar_key,
                states=tuple(slot.state for slot in availability.slots),
                busy_slot_count=availability.busy_slot_count,
                synthetic=True,
            )
        )

    slots: list[SchedulingSlot] = []
    for index, (day_offset, start_minute, end_minute) in enumerate(columns):
        column = tuple(
            (row.role, row.states[index]) for row in rows
        )
        free = tuple(
            role for role, state in column if state is AvailabilityState.FREE
        )
        conflicted = tuple(
            role for role, state in column if state is not AvailabilityState.FREE
        )
        blocking_required = tuple(
            role for role in conflicted if role is not ParticipantRole.OPTIONAL
        )
        if not conflicted:
            feasibility = SlotFeasibility.ALL_FREE
        elif not blocking_required:
            feasibility = SlotFeasibility.REQUIRED_FREE
        else:
            feasibility = SlotFeasibility.CONFLICTED
        slots.append(
            SchedulingSlot(
                day_offset=day_offset,
                start_minute_of_day=start_minute,
                end_minute_of_day=end_minute,
                feasibility=feasibility,
                free_participant_count=len(free),
                conflicted_participant_count=len(conflicted),
                synthetic=True,
            )
        )

    frozen_rows = tuple(rows)
    frozen_slots = tuple(slots)
    return SchedulingGrid(
        rows=frozen_rows,
        slots=frozen_slots,
        participant_count=len(frozen_rows),
        slot_count=len(frozen_slots),
        all_free_slot_count=sum(
            1 for slot in frozen_slots if slot.feasibility is SlotFeasibility.ALL_FREE
        ),
        required_free_slot_count=sum(
            1
            for slot in frozen_slots
            if slot.feasibility
            in (SlotFeasibility.ALL_FREE, SlotFeasibility.REQUIRED_FREE)
        ),
        synthetic=True,
    )


__all__ = [
    "ParticipantGridRow",
    "ParticipantRole",
    "SchedulingGrid",
    "SchedulingSlot",
    "SlotFeasibility",
    "SyntheticParticipant",
    "default_synthetic_participants",
    "read_fixture_scheduling_grid",
]
