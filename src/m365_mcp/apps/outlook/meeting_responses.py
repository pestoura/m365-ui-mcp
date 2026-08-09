"""Governed synthetic meeting response preparation for OUT-086."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from m365_mcp.apps.outlook.readiness import OutlookReadinessReport


class MeetingResponseKind(StrEnum):
    ACCEPT = "ACCEPT"
    TENTATIVE = "TENTATIVE"
    DECLINE = "DECLINE"


class MeetingResponseDisposition(StrEnum):
    PREPARED_NOT_SENT = "PREPARED_NOT_SENT"


@dataclass(frozen=True)
class SyntheticMeetingResponse:
    meeting_key: str
    response: MeetingResponseKind

    def __post_init__(self) -> None:
        _validate_key("meeting_key", self.meeting_key)

    def to_payload(self) -> dict[str, object]:
        return {"meeting_key": self.meeting_key, "response": self.response.value}


@dataclass(frozen=True)
class MeetingResponseResult:
    meeting_key: str
    response: MeetingResponseKind
    disposition: MeetingResponseDisposition
    changed: bool
    verified: bool
    response_sent: bool = False
    synthetic: bool = True


def _validate_key(name: str, value: str) -> None:
    if not value or value != value.strip() or any(char.isspace() for char in value):
        raise ValueError(f"{name} must be a non-empty semantic token")


def prepare_meeting_response(
    responses: tuple[SyntheticMeetingResponse, ...],
    desired: SyntheticMeetingResponse,
    *,
    readiness: OutlookReadinessReport,
    allow_outbound_prepare: bool = False,
) -> tuple[tuple[SyntheticMeetingResponse, ...], MeetingResponseResult]:
    """Prepare one synthetic response while keeping dispatch disabled."""
    if not readiness.ready_for_readonly_discovery:
        raise ValueError("Outlook read-only discovery is not ready")
    if not allow_outbound_prepare:
        raise PermissionError("meeting response requires explicit outbound-prepare allowance")
    keys = tuple(item.meeting_key for item in responses)
    if len(keys) != len(set(keys)):
        raise ValueError("meeting response catalog contains duplicate meeting_key values")

    current = next((item for item in responses if item.meeting_key == desired.meeting_key), None)
    if current is None:
        updated = (*responses, desired)
        changed = True
    else:
        updated = tuple(
            desired if item.meeting_key == desired.meeting_key else item
            for item in responses
        )
        changed = current != desired

    read_back = next(item for item in updated if item.meeting_key == desired.meeting_key)
    if read_back != desired:
        raise RuntimeError("synthetic read-back did not prove meeting response preparation")

    return updated, MeetingResponseResult(
        meeting_key=desired.meeting_key,
        response=desired.response,
        disposition=MeetingResponseDisposition.PREPARED_NOT_SENT,
        changed=changed,
        verified=True,
    )


__all__ = [
    "MeetingResponseDisposition",
    "MeetingResponseKind",
    "MeetingResponseResult",
    "SyntheticMeetingResponse",
    "prepare_meeting_response",
]
