"""Closed synthetic Outlook capability-difference reporting for OUT-119."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class CapabilityKind(StrEnum):
    MAIL_READ = "MAIL_READ"
    OUTBOUND_SEND = "OUTBOUND_SEND"
    CALENDAR_READ = "CALENDAR_READ"
    AUTOMATIC_REPLIES = "AUTOMATIC_REPLIES"


class CapabilitySurfaceState(StrEnum):
    AVAILABLE_SYNTHETIC = "AVAILABLE_SYNTHETIC"
    GOVERNED_NOT_EXECUTABLE = "GOVERNED_NOT_EXECUTABLE"
    PERMISSION_SCOPED = "PERMISSION_SCOPED"
    NOT_AVAILABLE = "NOT_AVAILABLE"


@dataclass(frozen=True)
class CapabilityDifferenceReport:
    capability: CapabilityKind
    primary_mailbox: CapabilitySurfaceState
    shared_mailbox: CapabilitySurfaceState
    delegated_send: CapabilitySurfaceState
    shared_calendar: CapabilitySurfaceState
    live_support_state: str = "UNOBSERVED"
    synthetic: bool = True

    def to_projection(self) -> dict[str, object]:
        return {
            "capability": self.capability.value,
            "primary_mailbox": self.primary_mailbox.value,
            "shared_mailbox": self.shared_mailbox.value,
            "delegated_send": self.delegated_send.value,
            "shared_calendar": self.shared_calendar.value,
            "live_support_state": self.live_support_state,
            "synthetic": True,
        }


_MATRIX: dict[
    CapabilityKind,
    tuple[
        CapabilitySurfaceState,
        CapabilitySurfaceState,
        CapabilitySurfaceState,
        CapabilitySurfaceState,
    ],
] = {
    CapabilityKind.MAIL_READ: (
        CapabilitySurfaceState.AVAILABLE_SYNTHETIC,
        CapabilitySurfaceState.AVAILABLE_SYNTHETIC,
        CapabilitySurfaceState.NOT_AVAILABLE,
        CapabilitySurfaceState.NOT_AVAILABLE,
    ),
    CapabilityKind.OUTBOUND_SEND: (
        CapabilitySurfaceState.GOVERNED_NOT_EXECUTABLE,
        CapabilitySurfaceState.GOVERNED_NOT_EXECUTABLE,
        CapabilitySurfaceState.GOVERNED_NOT_EXECUTABLE,
        CapabilitySurfaceState.NOT_AVAILABLE,
    ),
    CapabilityKind.CALENDAR_READ: (
        CapabilitySurfaceState.AVAILABLE_SYNTHETIC,
        CapabilitySurfaceState.NOT_AVAILABLE,
        CapabilitySurfaceState.NOT_AVAILABLE,
        CapabilitySurfaceState.PERMISSION_SCOPED,
    ),
    CapabilityKind.AUTOMATIC_REPLIES: (
        CapabilitySurfaceState.AVAILABLE_SYNTHETIC,
        CapabilitySurfaceState.AVAILABLE_SYNTHETIC,
        CapabilitySurfaceState.NOT_AVAILABLE,
        CapabilitySurfaceState.NOT_AVAILABLE,
    ),
}


def report_capability_difference(
    capability: CapabilityKind,
) -> CapabilityDifferenceReport:
    """Return one explicit static synthetic capability comparison."""
    if not isinstance(capability, CapabilityKind):
        raise ValueError("capability must be a closed CapabilityKind")
    primary, shared, delegated, calendar = _MATRIX[capability]
    return CapabilityDifferenceReport(
        capability=capability,
        primary_mailbox=primary,
        shared_mailbox=shared,
        delegated_send=delegated,
        shared_calendar=calendar,
    )


__all__ = [
    "CapabilityDifferenceReport",
    "CapabilityKind",
    "CapabilitySurfaceState",
    "report_capability_difference",
]
