"""Synthetic-only Outlook common-slot search for OUT-092.

The search composes the bounded synthetic Scheduling Assistant grid and returns
relative slot coordinates only. It performs no booking, directory lookup, live
query or mutation and carries no tenant identity, address, URL, selector,
session material, token or cookie.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from m365_mcp.apps.outlook.availability_reads import AvailabilityWindow
from m365_mcp.apps.outlook.calendar_events import SyntheticEvent
from m365_mcp.apps.outlook.calendar_list import SyntheticCalendar
from m365_mcp.apps.outlook.mock_ui import OutlookMockFixture
from m365_mcp.apps.outlook.readiness import OutlookReadinessReport
from m365_mcp.apps.outlook.scheduling_assistant import (
    SchedulingGrid,
    SlotFeasibility,
    SyntheticParticipant,
    read_fixture_scheduling_grid,
)

_MAX_RESULTS = 50


class CommonSlotRequirement(StrEnum):
    """Closed feasibility requirements for synthetic common-slot matching."""

    ALL_FREE = "ALL_FREE"
    REQUIRED_FREE = "REQUIRED_FREE"


@dataclass(frozen=True)
class CommonSlotRequest:
    """Bounded common-slot search request."""

    requirement: CommonSlotRequirement = CommonSlotRequirement.ALL_FREE
    max_results: int = 10

    def __post_init__(self) -> None:
        if not isinstance(self.requirement, CommonSlotRequirement):
            raise ValueError("requirement must be a closed CommonSlotRequirement")
        if self.max_results <= 0 or self.max_results > _MAX_RESULTS:
            raise ValueError("max_results must be a bounded positive count")


@dataclass(frozen=True)
class CommonSlotCandidate:
    """One relative common-slot candidate."""

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
class CommonSlotResult:
    """Bounded deterministic common-slot result."""

    candidates: tuple[CommonSlotCandidate, ...]
    evaluated_slot_count: int
    matching_slot_count: int
    requirement: CommonSlotRequirement
    has_more: bool
    synthetic: bool


def _matches(feasibility: SlotFeasibility, requirement: CommonSlotRequirement) -> bool:
    if requirement is CommonSlotRequirement.ALL_FREE:
        return feasibility is SlotFeasibility.ALL_FREE
    return feasibility in (SlotFeasibility.ALL_FREE, SlotFeasibility.REQUIRED_FREE)


def _candidate_from_grid_slot(grid: SchedulingGrid, index: int) -> CommonSlotCandidate:
    slot = grid.slots[index]
    return CommonSlotCandidate(
        day_offset=slot.day_offset,
        start_minute_of_day=slot.start_minute_of_day,
        end_minute_of_day=slot.end_minute_of_day,
        feasibility=slot.feasibility,
        free_participant_count=slot.free_participant_count,
        conflicted_participant_count=slot.conflicted_participant_count,
        synthetic=True,
    )


def find_fixture_common_slots(
    fixture: OutlookMockFixture,
    window: AvailabilityWindow,
    request: CommonSlotRequest,
    *,
    readiness: OutlookReadinessReport,
    participants: tuple[SyntheticParticipant, ...] | None = None,
    events: tuple[SyntheticEvent, ...] | None = None,
    calendars: tuple[SyntheticCalendar, ...] | None = None,
) -> CommonSlotResult:
    """Find bounded common slots by composing the synthetic Scheduling Assistant."""
    if not isinstance(request, CommonSlotRequest):
        raise ValueError("request must be a bounded CommonSlotRequest")
    grid = read_fixture_scheduling_grid(
        fixture,
        window,
        readiness=readiness,
        participants=participants,
        events=events,
        calendars=calendars,
    )
    matching = tuple(
        _candidate_from_grid_slot(grid, index)
        for index, slot in enumerate(grid.slots)
        if _matches(slot.feasibility, request.requirement)
    )
    ordered = tuple(
        sorted(
            matching,
            key=lambda item: (item.day_offset, item.start_minute_of_day),
        )
    )
    selected = ordered[: request.max_results]
    return CommonSlotResult(
        candidates=selected,
        evaluated_slot_count=grid.slot_count,
        matching_slot_count=len(ordered),
        requirement=request.requirement,
        has_more=len(ordered) > len(selected),
        synthetic=True,
    )


__all__ = [
    "CommonSlotCandidate",
    "CommonSlotRequest",
    "CommonSlotRequirement",
    "CommonSlotResult",
    "find_fixture_common_slots",
]
