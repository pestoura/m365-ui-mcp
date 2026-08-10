"""Governed synthetic OOO existing-meeting cancellation intents for OUT-135."""

from __future__ import annotations

from dataclasses import dataclass

from m365_mcp.apps.outlook.ooo_schedule import OooSchedule
from m365_mcp.apps.outlook.outbound_models import OutboundApprovalState
from m365_mcp.apps.outlook.readiness import OutlookReadinessReport

_MAX_EVENT_KEYS = 50


def _event_key(value: str) -> str:
    if not value or value != value.strip() or any(char.isspace() for char in value):
        raise ValueError("event_key must be a non-empty semantic token")
    if "@" in value or "://" in value or "/" in value:
        raise ValueError("event_key must be opaque and must not encode an address or URL")
    return value


@dataclass(frozen=True)
class OooMeetingCancellationIntent:
    intent_key: str
    event_keys: tuple[str, ...]
    schedule: OooSchedule
    approval_state: OutboundApprovalState = OutboundApprovalState.REQUIRED_NOT_BOUND
    dispatched: bool = False
    synthetic: bool = True
    live_support_state: str = "UNOBSERVED"

    def __post_init__(self) -> None:
        if not self.intent_key or self.intent_key != self.intent_key.strip():
            raise ValueError("intent_key must be a non-empty semantic token")
        if len(self.event_keys) == 0 or len(self.event_keys) > _MAX_EVENT_KEYS:
            raise ValueError("event_keys must be a bounded non-empty tuple")
        if len(self.event_keys) != len(set(self.event_keys)):
            raise ValueError("event_keys must be unique")
        for key in self.event_keys:
            _event_key(key)
        if not self.schedule.synthetic or self.schedule.live_support_state != "UNOBSERVED":
            raise ValueError("meeting cancellation requires a synthetic relative schedule")
        if not self.synthetic or self.live_support_state != "UNOBSERVED":
            raise ValueError("OOO cancellation intent must remain synthetic and live-unobserved")

    @property
    def executable(self) -> bool:
        return False

    def to_projection(self) -> dict[str, object]:
        return {
            "intent_key": self.intent_key,
            "event_keys": self.event_keys,
            "approval_state": self.approval_state.value,
            "approval_required": True,
            "executable": False,
            "dispatched": False,
            "synthetic": True,
            "live_support_state": self.live_support_state,
        }


def prepare_ooo_meeting_cancellations(
    *,
    intent_key: str,
    event_keys: tuple[str, ...],
    schedule: OooSchedule,
    readiness: OutlookReadinessReport,
) -> OooMeetingCancellationIntent:
    """Prepare bounded cancellation intent only; never cancel or notify attendees."""
    if not readiness.ready_for_readonly_discovery:
        raise ValueError("Outlook read-only discovery is not ready")
    intent = OooMeetingCancellationIntent(intent_key, event_keys, schedule)
    if intent.executable or intent.dispatched:
        raise RuntimeError("synthetic OOO cancellation unexpectedly became executable")
    return intent


__all__ = ["OooMeetingCancellationIntent", "prepare_ooo_meeting_cancellations"]
