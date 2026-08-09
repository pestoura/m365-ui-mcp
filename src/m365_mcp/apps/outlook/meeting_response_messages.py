"""Governed synthetic meeting response-with-message preparation for OUT-087."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from m365_mcp.apps.outlook.readiness import OutlookReadinessReport

_MAX_MESSAGE_CHARS = 4000


class MeetingResponseMessageKind(StrEnum):
    ACCEPT = "ACCEPT"
    TENTATIVE = "TENTATIVE"
    DECLINE = "DECLINE"


@dataclass(frozen=True)
class SyntheticMeetingResponseMessage:
    meeting_key: str
    response: MeetingResponseMessageKind
    message_text: str

    def __post_init__(self) -> None:
        _validate_key("meeting_key", self.meeting_key)
        if "\x00" in self.message_text:
            raise ValueError("message_text must not contain NUL")
        if len(self.message_text) > _MAX_MESSAGE_CHARS:
            raise ValueError("message_text exceeds bounded synthetic size")

    def to_payload(self) -> dict[str, object]:
        return {
            "meeting_key": self.meeting_key,
            "response": self.response.value,
            "message_text": self.message_text,
        }


@dataclass(frozen=True)
class MeetingResponseMessageResult:
    meeting_key: str
    response: MeetingResponseMessageKind
    changed: bool
    verified: bool
    response_sent: bool = False
    synthetic: bool = True


def _validate_key(name: str, value: str) -> None:
    if not value or value != value.strip() or any(char.isspace() for char in value):
        raise ValueError(f"{name} must be a non-empty semantic token")


def prepare_response_with_message(
    messages: tuple[SyntheticMeetingResponseMessage, ...],
    desired: SyntheticMeetingResponseMessage,
    *,
    readiness: OutlookReadinessReport,
    allow_outbound_prepare: bool = False,
) -> tuple[tuple[SyntheticMeetingResponseMessage, ...], MeetingResponseMessageResult]:
    """Prepare response text with exact synthetic read-back and no dispatch."""
    if not readiness.ready_for_readonly_discovery:
        raise ValueError("Outlook read-only discovery is not ready")
    if not allow_outbound_prepare:
        raise PermissionError("response message requires explicit outbound-prepare allowance")
    keys = tuple(item.meeting_key for item in messages)
    if len(keys) != len(set(keys)):
        raise ValueError("response message catalog contains duplicate meeting_key values")

    current = next((item for item in messages if item.meeting_key == desired.meeting_key), None)
    if current is None:
        updated = (*messages, desired)
        changed = True
    else:
        updated = tuple(
            desired if item.meeting_key == desired.meeting_key else item for item in messages
        )
        changed = current != desired

    read_back = next(item for item in updated if item.meeting_key == desired.meeting_key)
    if read_back != desired:
        raise RuntimeError("synthetic read-back did not prove response message preparation")

    return updated, MeetingResponseMessageResult(
        meeting_key=desired.meeting_key,
        response=desired.response,
        changed=changed,
        verified=True,
    )


__all__ = [
    "MeetingResponseMessageKind",
    "MeetingResponseMessageResult",
    "SyntheticMeetingResponseMessage",
    "prepare_response_with_message",
]
