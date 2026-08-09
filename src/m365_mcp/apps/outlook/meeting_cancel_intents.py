"""Governed synthetic meeting cancellation preparation for OUT-090."""

from __future__ import annotations

from dataclasses import dataclass

from m365_mcp.apps.outlook.readiness import OutlookReadinessReport

_MAX_MESSAGE_CHARS = 4000


@dataclass(frozen=True)
class SyntheticMeetingCancellationIntent:
    meeting_key: str
    message_text: str | None = None

    def __post_init__(self) -> None:
        _validate_key("meeting_key", self.meeting_key)
        if self.message_text is not None:
            if "\x00" in self.message_text:
                raise ValueError("message_text must not contain NUL")
            if len(self.message_text) > _MAX_MESSAGE_CHARS:
                raise ValueError("message_text exceeds bounded synthetic size")

    def to_payload(self) -> dict[str, object]:
        return {"meeting_key": self.meeting_key, "message_text": self.message_text}


@dataclass(frozen=True)
class MeetingCancellationResult:
    meeting_key: str
    verified: bool
    cancelled: bool = False
    cancellation_sent: bool = False
    synthetic: bool = True


def _validate_key(name: str, value: str) -> None:
    if not value or value != value.strip() or any(char.isspace() for char in value):
        raise ValueError(f"{name} must be a non-empty semantic token")


def prepare_meeting_cancellation(
    intents: tuple[SyntheticMeetingCancellationIntent, ...],
    desired: SyntheticMeetingCancellationIntent,
    *,
    readiness: OutlookReadinessReport,
    allow_outbound_prepare: bool = False,
    allow_cancellation_prepare: bool = False,
) -> tuple[tuple[SyntheticMeetingCancellationIntent, ...], MeetingCancellationResult]:
    """Prepare cancellation intent while leaving meeting state untouched."""
    if not readiness.ready_for_readonly_discovery:
        raise ValueError("Outlook read-only discovery is not ready")
    if not allow_outbound_prepare:
        raise PermissionError("meeting cancellation requires outbound-prepare allowance")
    if not allow_cancellation_prepare:
        raise PermissionError("meeting cancellation requires cancellation-prepare allowance")

    current = next((item for item in intents if item.meeting_key == desired.meeting_key), None)
    if current is None:
        updated = (*intents, desired)
    else:
        updated = tuple(
            desired if item.meeting_key == desired.meeting_key else item for item in intents
        )
    keys = tuple(item.meeting_key for item in updated)
    if len(keys) != len(set(keys)):
        raise ValueError("cancellation catalog contains duplicate meeting_key values")
    read_back = next(item for item in updated if item.meeting_key == desired.meeting_key)
    if read_back != desired:
        raise RuntimeError("synthetic read-back did not prove cancellation preparation")

    return updated, MeetingCancellationResult(
        meeting_key=desired.meeting_key,
        verified=True,
    )


__all__ = [
    "MeetingCancellationResult",
    "SyntheticMeetingCancellationIntent",
    "prepare_meeting_cancellation",
]
