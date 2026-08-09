"""Read-side synthetic organizer response tracking for OUT-091."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from m365_mcp.apps.outlook.readiness import OutlookReadinessReport

_MAX_TRACKING_RECORDS = 500


class TrackedMeetingResponse(StrEnum):
    NONE = "NONE"
    ACCEPTED = "ACCEPTED"
    TENTATIVE = "TENTATIVE"
    DECLINED = "DECLINED"


@dataclass(frozen=True)
class SyntheticOrganizerResponseRecord:
    meeting_key: str
    participant_key: str
    response: TrackedMeetingResponse

    def __post_init__(self) -> None:
        _validate_key("meeting_key", self.meeting_key)
        _validate_key("participant_key", self.participant_key)
        if "@" in self.participant_key:
            raise ValueError("participant_key must not contain an email address")


@dataclass(frozen=True)
class OrganizerResponseSummary:
    meeting_key: str
    total: int
    none: int
    accepted: int
    tentative: int
    declined: int
    synthetic: bool = True


def _validate_key(name: str, value: str) -> None:
    if not value or value != value.strip() or any(char.isspace() for char in value):
        raise ValueError(f"{name} must be a non-empty semantic token")


def list_organizer_responses(
    records: tuple[SyntheticOrganizerResponseRecord, ...],
    *,
    meeting_key: str,
    readiness: OutlookReadinessReport,
) -> tuple[SyntheticOrganizerResponseRecord, ...]:
    """Return deterministic synthetic response records for one meeting."""
    if not readiness.ready_for_readonly_discovery:
        raise ValueError("Outlook read-only discovery is not ready")
    _validate_key("meeting_key", meeting_key)
    if len(records) > _MAX_TRACKING_RECORDS:
        raise ValueError("response tracking catalog exceeds bounded size")
    identities = tuple((item.meeting_key, item.participant_key) for item in records)
    if len(identities) != len(set(identities)):
        raise ValueError("response tracking catalog contains duplicate participant identity")
    selected = tuple(item for item in records if item.meeting_key == meeting_key)
    return tuple(sorted(selected, key=lambda item: item.participant_key))


def summarize_organizer_responses(
    records: tuple[SyntheticOrganizerResponseRecord, ...],
    *,
    meeting_key: str,
    readiness: OutlookReadinessReport,
) -> OrganizerResponseSummary:
    selected = list_organizer_responses(
        records,
        meeting_key=meeting_key,
        readiness=readiness,
    )
    counts = {value: 0 for value in TrackedMeetingResponse}
    for item in selected:
        counts[item.response] += 1
    return OrganizerResponseSummary(
        meeting_key=meeting_key,
        total=len(selected),
        none=counts[TrackedMeetingResponse.NONE],
        accepted=counts[TrackedMeetingResponse.ACCEPTED],
        tentative=counts[TrackedMeetingResponse.TENTATIVE],
        declined=counts[TrackedMeetingResponse.DECLINED],
    )


__all__ = [
    "OrganizerResponseSummary",
    "SyntheticOrganizerResponseRecord",
    "TrackedMeetingResponse",
    "list_organizer_responses",
    "summarize_organizer_responses",
]
