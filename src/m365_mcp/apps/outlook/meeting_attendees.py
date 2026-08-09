"""Governed synthetic attendee/optional/resource management for OUT-082."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from m365_mcp.apps.outlook.readiness import OutlookReadinessReport
from m365_mcp.apps.outlook.recipient_resolution import SyntheticRecipientCandidate

_MAX_ATTENDEES = 100


class AttendeeRole(StrEnum):
    REQUIRED = "REQUIRED"
    OPTIONAL = "OPTIONAL"
    RESOURCE = "RESOURCE"


class AttendeeMutationAction(StrEnum):
    UPSERT = "UPSERT"
    REMOVE = "REMOVE"


@dataclass(frozen=True)
class SyntheticMeetingAttendee:
    meeting_key: str
    participant_key: str
    role: AttendeeRole

    def __post_init__(self) -> None:
        _validate_key("meeting_key", self.meeting_key)
        _validate_key("participant_key", self.participant_key)
        if "@" in self.participant_key:
            raise ValueError("participant_key must not contain an email address")


@dataclass(frozen=True)
class AttendeeMutationRequest:
    action: AttendeeMutationAction
    meeting_key: str
    participant_key: str
    role: AttendeeRole | None = None

    def __post_init__(self) -> None:
        _validate_key("meeting_key", self.meeting_key)
        _validate_key("participant_key", self.participant_key)
        if "@" in self.participant_key:
            raise ValueError("participant_key must not contain an email address")
        if self.action is AttendeeMutationAction.UPSERT and self.role is None:
            raise ValueError("upsert requires role")
        if self.action is AttendeeMutationAction.REMOVE and self.role is not None:
            raise ValueError("remove must not include role")

    def to_payload(self) -> dict[str, object]:
        return {
            "action": self.action.value,
            "meeting_key": self.meeting_key,
            "participant_key": self.participant_key,
            "role": None if self.role is None else self.role.value,
        }


@dataclass(frozen=True)
class AttendeeMutationResult:
    meeting_key: str
    participant_key: str
    changed: bool
    verified: bool
    invitation_sent: bool = False
    synthetic: bool = True


def _validate_key(name: str, value: str) -> None:
    if not value or value != value.strip() or any(char.isspace() for char in value):
        raise ValueError(f"{name} must be a non-empty semantic token")


def _validate_candidate(
    participant_key: str,
    candidates: tuple[SyntheticRecipientCandidate, ...],
) -> None:
    matches = tuple(item for item in candidates if item.recipient_key == participant_key)
    if len(matches) != 1:
        raise ValueError("participant_key must resolve to exactly one known candidate")


def mutate_meeting_attendees(
    attendees: tuple[SyntheticMeetingAttendee, ...],
    request: AttendeeMutationRequest,
    *,
    readiness: OutlookReadinessReport,
    candidates: tuple[SyntheticRecipientCandidate, ...],
    allow_outbound_prepare: bool = False,
) -> tuple[tuple[SyntheticMeetingAttendee, ...], AttendeeMutationResult]:
    """Mutate synthetic attendees while keeping invitation dispatch disabled."""
    if not readiness.ready_for_readonly_discovery:
        raise ValueError("Outlook read-only discovery is not ready")
    if not allow_outbound_prepare:
        raise PermissionError("attendee mutation requires explicit outbound-prepare allowance")
    if len(attendees) > _MAX_ATTENDEES:
        raise ValueError("attendee catalog exceeds bounded size")
    _validate_candidate(request.participant_key, candidates)

    identity = (request.meeting_key, request.participant_key)
    matches = tuple(
        item
        for item in attendees
        if (item.meeting_key, item.participant_key) == identity
    )
    if len(matches) > 1:
        raise ValueError("attendee catalog contains duplicate participant identity")

    if request.action is AttendeeMutationAction.UPSERT:
        assert request.role is not None
        replacement = SyntheticMeetingAttendee(
            meeting_key=request.meeting_key,
            participant_key=request.participant_key,
            role=request.role,
        )
        if matches:
            updated = tuple(
                replacement
                if (item.meeting_key, item.participant_key) == identity
                else item
                for item in attendees
            )
            changed = matches[0] != replacement
        else:
            if len(attendees) >= _MAX_ATTENDEES:
                raise ValueError("attendee catalog is full")
            updated = (*attendees, replacement)
            changed = True
        read_back = next(
            item
            for item in updated
            if (item.meeting_key, item.participant_key) == identity
        )
        if read_back != replacement:
            raise RuntimeError("synthetic read-back did not prove attendee state")
    else:
        updated = tuple(
            item
            for item in attendees
            if (item.meeting_key, item.participant_key) != identity
        )
        changed = bool(matches)
        if any(
            (item.meeting_key, item.participant_key) == identity for item in updated
        ):
            raise RuntimeError("synthetic read-back did not prove attendee removal")

    return updated, AttendeeMutationResult(
        meeting_key=request.meeting_key,
        participant_key=request.participant_key,
        changed=changed,
        verified=True,
    )


__all__ = [
    "AttendeeMutationAction",
    "AttendeeMutationRequest",
    "AttendeeMutationResult",
    "AttendeeRole",
    "SyntheticMeetingAttendee",
    "mutate_meeting_attendees",
]
