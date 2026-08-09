"""Governed synthetic meeting-forward preparation for OUT-089."""

from __future__ import annotations

from dataclasses import dataclass

from m365_mcp.apps.outlook.readiness import OutlookReadinessReport
from m365_mcp.apps.outlook.recipient_resolution import SyntheticRecipientCandidate

_MAX_RECIPIENTS = 50


@dataclass(frozen=True)
class SyntheticMeetingForwardIntent:
    meeting_key: str
    recipient_keys: tuple[str, ...]

    def __post_init__(self) -> None:
        _validate_key("meeting_key", self.meeting_key)
        if not self.recipient_keys:
            raise ValueError("recipient_keys must not be empty")
        if len(self.recipient_keys) > _MAX_RECIPIENTS:
            raise ValueError("recipient_keys exceeds bounded size")
        if len(self.recipient_keys) != len(set(self.recipient_keys)):
            raise ValueError("recipient_keys must be unique")
        for key in self.recipient_keys:
            _validate_key("recipient_key", key)
            if "@" in key:
                raise ValueError("recipient_key must not contain an email address")

    def to_payload(self) -> dict[str, object]:
        return {
            "meeting_key": self.meeting_key,
            "recipient_keys": self.recipient_keys,
        }


@dataclass(frozen=True)
class MeetingForwardResult:
    meeting_key: str
    recipient_keys: tuple[str, ...]
    verified: bool
    forwarded: bool = False
    synthetic: bool = True


def _validate_key(name: str, value: str) -> None:
    if not value or value != value.strip() or any(char.isspace() for char in value):
        raise ValueError(f"{name} must be a non-empty semantic token")


def _validate_recipients(
    recipient_keys: tuple[str, ...],
    candidates: tuple[SyntheticRecipientCandidate, ...],
) -> None:
    known = {item.recipient_key for item in candidates}
    for key in recipient_keys:
        if key not in known:
            raise ValueError("recipient_key must resolve to a known synthetic candidate")


def prepare_meeting_forward(
    intents: tuple[SyntheticMeetingForwardIntent, ...],
    desired: SyntheticMeetingForwardIntent,
    *,
    readiness: OutlookReadinessReport,
    candidates: tuple[SyntheticRecipientCandidate, ...],
    allow_outbound_prepare: bool = False,
) -> tuple[tuple[SyntheticMeetingForwardIntent, ...], MeetingForwardResult]:
    """Prepare a meeting forward with semantic recipients and no dispatch."""
    if not readiness.ready_for_readonly_discovery:
        raise ValueError("Outlook read-only discovery is not ready")
    if not allow_outbound_prepare:
        raise PermissionError("meeting forward requires explicit outbound-prepare allowance")
    _validate_recipients(desired.recipient_keys, candidates)

    current = next((item for item in intents if item.meeting_key == desired.meeting_key), None)
    if current is None:
        updated = (*intents, desired)
    else:
        updated = tuple(
            desired if item.meeting_key == desired.meeting_key else item for item in intents
        )
    keys = tuple(item.meeting_key for item in updated)
    if len(keys) != len(set(keys)):
        raise ValueError("meeting forward catalog contains duplicate meeting_key values")
    read_back = next(item for item in updated if item.meeting_key == desired.meeting_key)
    if read_back != desired:
        raise RuntimeError("synthetic read-back did not prove meeting forward preparation")

    return updated, MeetingForwardResult(
        meeting_key=desired.meeting_key,
        recipient_keys=desired.recipient_keys,
        verified=True,
    )


__all__ = [
    "MeetingForwardResult",
    "SyntheticMeetingForwardIntent",
    "prepare_meeting_forward",
]
