"""Governed tenant-neutral synthetic meeting create/update for OUT-081."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from m365_mcp.apps.outlook.calendar_events import SyntheticEvent
from m365_mcp.apps.outlook.readiness import OutlookReadinessReport


class MeetingMutationAction(StrEnum):
    CREATE = "CREATE"
    UPDATE = "UPDATE"


class MeetingMutationDisposition(StrEnum):
    PREPARED_NOT_SENT = "PREPARED_NOT_SENT"


@dataclass(frozen=True)
class SyntheticMeeting:
    meeting_key: str
    event: SyntheticEvent

    def __post_init__(self) -> None:
        _validate_key("meeting_key", self.meeting_key)
        if self.event.is_cancelled:
            raise ValueError("meeting definition cannot reference a cancelled event")


@dataclass(frozen=True)
class MeetingMutationRequest:
    action: MeetingMutationAction
    meeting: SyntheticMeeting

    def to_payload(self) -> dict[str, object]:
        event = self.meeting.event
        return {
            "action": self.action.value,
            "meeting_key": self.meeting.meeting_key,
            "event_key": event.event_key,
            "calendar_key": event.calendar_key,
            "subject": event.subject,
            "start_day_offset": event.start_day_offset,
            "start_minute_of_day": event.start_minute_of_day,
            "duration_minutes": event.duration_minutes,
            "is_all_day": event.is_all_day,
        }


@dataclass(frozen=True)
class MeetingMutationResult:
    action: MeetingMutationAction
    meeting_key: str
    disposition: MeetingMutationDisposition
    changed: bool
    verified: bool
    read_back: SyntheticMeeting
    invitation_sent: bool = False
    synthetic: bool = True


def _validate_key(name: str, value: str) -> None:
    if not value or value != value.strip() or any(char.isspace() for char in value):
        raise ValueError(f"{name} must be a non-empty semantic token")


def prepare_meeting_mutation(
    meetings: tuple[SyntheticMeeting, ...],
    request: MeetingMutationRequest,
    *,
    readiness: OutlookReadinessReport,
    allow_outbound_prepare: bool = False,
) -> tuple[tuple[SyntheticMeeting, ...], MeetingMutationResult]:
    """Prepare one meeting definition; never dispatch an invitation."""
    if not readiness.ready_for_readonly_discovery:
        raise ValueError("Outlook read-only discovery is not ready")
    if not allow_outbound_prepare:
        raise PermissionError("meeting definition requires explicit outbound-prepare allowance")

    keys = tuple(item.meeting_key for item in meetings)
    if len(keys) != len(set(keys)):
        raise ValueError("meeting catalog contains duplicate meeting_key values")
    meeting_key = request.meeting.meeting_key
    current = next((item for item in meetings if item.meeting_key == meeting_key), None)

    if request.action is MeetingMutationAction.CREATE:
        if current is not None:
            raise ValueError("create requires a new meeting_key")
        updated = (*meetings, request.meeting)
        changed = True
    else:
        if current is None:
            raise ValueError("update requires an existing meeting_key")
        updated = tuple(
            request.meeting if item.meeting_key == meeting_key else item for item in meetings
        )
        changed = current != request.meeting

    read_back = next(item for item in updated if item.meeting_key == meeting_key)
    if read_back != request.meeting:
        raise RuntimeError("synthetic read-back did not prove meeting definition")

    return updated, MeetingMutationResult(
        action=request.action,
        meeting_key=meeting_key,
        disposition=MeetingMutationDisposition.PREPARED_NOT_SENT,
        changed=changed,
        verified=True,
        read_back=read_back,
    )


__all__ = [
    "MeetingMutationAction",
    "MeetingMutationDisposition",
    "MeetingMutationRequest",
    "MeetingMutationResult",
    "SyntheticMeeting",
    "prepare_meeting_mutation",
]
