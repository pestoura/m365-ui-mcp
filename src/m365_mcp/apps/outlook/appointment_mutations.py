"""Tenant-neutral synthetic appointment CRUD for OUT-080."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from m365_mcp.apps.outlook.calendar_events import SyntheticEvent
from m365_mcp.apps.outlook.readiness import OutlookReadinessReport

_MAX_EVENTS = 500


class AppointmentMutationAction(StrEnum):
    CREATE = "CREATE"
    UPDATE = "UPDATE"
    DELETE = "DELETE"


@dataclass(frozen=True)
class AppointmentMutationRequest:
    action: AppointmentMutationAction
    event: SyntheticEvent | None = None
    event_key: str | None = None

    def __post_init__(self) -> None:
        if self.action in {
            AppointmentMutationAction.CREATE,
            AppointmentMutationAction.UPDATE,
        }:
            if self.event is None or self.event_key is not None:
                raise ValueError("create/update requires event and no event_key")
            if self.event.is_cancelled:
                raise ValueError("appointment mutation cannot write a cancelled event")
        elif self.action is AppointmentMutationAction.DELETE:
            if self.event is not None or self.event_key is None:
                raise ValueError("delete requires event_key and no event")
            _validate_key(self.event_key)

    def to_payload(self) -> dict[str, object]:
        event_payload: dict[str, object] | None = None
        if self.event is not None:
            event_payload = {
                "event_key": self.event.event_key,
                "calendar_key": self.event.calendar_key,
                "subject": self.event.subject,
                "start_day_offset": self.event.start_day_offset,
                "start_minute_of_day": self.event.start_minute_of_day,
                "duration_minutes": self.event.duration_minutes,
                "is_all_day": self.event.is_all_day,
                "show_as": self.event.show_as.value,
                "sensitivity": self.event.sensitivity.value,
            }
        return {
            "action": self.action.value,
            "event": event_payload,
            "event_key": self.event_key,
        }


@dataclass(frozen=True)
class AppointmentMutationResult:
    action: AppointmentMutationAction
    event_key: str
    changed: bool
    verified: bool
    read_back: SyntheticEvent | None
    synthetic: bool = True


def _validate_key(value: str) -> None:
    if not value or value != value.strip() or any(char.isspace() for char in value):
        raise ValueError("event_key must be a non-empty semantic token")


def mutate_appointments(
    events: tuple[SyntheticEvent, ...],
    request: AppointmentMutationRequest,
    *,
    readiness: OutlookReadinessReport,
) -> tuple[tuple[SyntheticEvent, ...], AppointmentMutationResult]:
    """Apply one synthetic appointment mutation with exact read-back."""
    if not readiness.ready_for_readonly_discovery:
        raise ValueError("Outlook read-only discovery is not ready")
    if len(events) > _MAX_EVENTS:
        raise ValueError("event catalog exceeds bounded size")
    keys = tuple(item.event_key for item in events)
    if len(keys) != len(set(keys)):
        raise ValueError("event catalog contains duplicate event_key values")

    if request.action is AppointmentMutationAction.CREATE:
        assert request.event is not None
        event_key = request.event.event_key
        if event_key in keys:
            raise ValueError("create requires a new event_key")
        if len(events) >= _MAX_EVENTS:
            raise ValueError("event catalog is full")
        updated = (*events, request.event)
        changed = True
    elif request.action is AppointmentMutationAction.UPDATE:
        assert request.event is not None
        event_key = request.event.event_key
        current = next((item for item in events if item.event_key == event_key), None)
        if current is None:
            raise ValueError("update requires an existing event_key")
        updated = tuple(request.event if item.event_key == event_key else item for item in events)
        changed = current != request.event
    else:
        assert request.event_key is not None
        event_key = request.event_key
        updated = tuple(item for item in events if item.event_key != event_key)
        changed = len(updated) != len(events)

    read_back = next((item for item in updated if item.event_key == event_key), None)
    if request.action is AppointmentMutationAction.DELETE:
        if read_back is not None:
            raise RuntimeError("synthetic read-back did not prove appointment deletion")
    elif read_back != request.event:
        raise RuntimeError("synthetic read-back did not prove appointment state")

    return updated, AppointmentMutationResult(
        action=request.action,
        event_key=event_key,
        changed=changed,
        verified=True,
        read_back=read_back,
    )


__all__ = [
    "AppointmentMutationAction",
    "AppointmentMutationRequest",
    "AppointmentMutationResult",
    "mutate_appointments",
]
