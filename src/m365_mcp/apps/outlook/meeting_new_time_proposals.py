"""Governed synthetic new-time proposal preparation for OUT-088."""

from __future__ import annotations

from dataclasses import dataclass

from m365_mcp.apps.outlook.readiness import OutlookReadinessReport

_MAX_DURATION_MINUTES = 24 * 60


@dataclass(frozen=True)
class SyntheticNewTimeProposal:
    meeting_key: str
    start_day_offset: int
    start_minute_of_day: int
    duration_minutes: int

    def __post_init__(self) -> None:
        _validate_key("meeting_key", self.meeting_key)
        if not isinstance(self.start_day_offset, int) or isinstance(
            self.start_day_offset, bool
        ):
            raise ValueError("start_day_offset must be an integer")
        if not isinstance(self.start_minute_of_day, int) or isinstance(
            self.start_minute_of_day, bool
        ):
            raise ValueError("start_minute_of_day must be an integer")
        if not 0 <= self.start_minute_of_day < 24 * 60:
            raise ValueError("start_minute_of_day must be within a day")
        if not isinstance(self.duration_minutes, int) or isinstance(
            self.duration_minutes, bool
        ):
            raise ValueError("duration_minutes must be an integer")
        if not 1 <= self.duration_minutes <= _MAX_DURATION_MINUTES:
            raise ValueError("duration_minutes exceeds bounded synthetic range")

    def to_payload(self) -> dict[str, object]:
        return {
            "meeting_key": self.meeting_key,
            "start_day_offset": self.start_day_offset,
            "start_minute_of_day": self.start_minute_of_day,
            "duration_minutes": self.duration_minutes,
        }


@dataclass(frozen=True)
class NewTimeProposalResult:
    meeting_key: str
    changed: bool
    verified: bool
    proposal_sent: bool = False
    synthetic: bool = True


def _validate_key(name: str, value: str) -> None:
    if not value or value != value.strip() or any(char.isspace() for char in value):
        raise ValueError(f"{name} must be a non-empty semantic token")


def prepare_new_time_proposal(
    proposals: tuple[SyntheticNewTimeProposal, ...],
    desired: SyntheticNewTimeProposal,
    *,
    readiness: OutlookReadinessReport,
    allow_outbound_prepare: bool = False,
) -> tuple[tuple[SyntheticNewTimeProposal, ...], NewTimeProposalResult]:
    """Prepare a proposed time with exact read-back and no live response."""
    if not readiness.ready_for_readonly_discovery:
        raise ValueError("Outlook read-only discovery is not ready")
    if not allow_outbound_prepare:
        raise PermissionError("new-time proposal requires explicit outbound-prepare allowance")
    keys = tuple(item.meeting_key for item in proposals)
    if len(keys) != len(set(keys)):
        raise ValueError("proposal catalog contains duplicate meeting_key values")

    current = next((item for item in proposals if item.meeting_key == desired.meeting_key), None)
    if current is None:
        updated = (*proposals, desired)
        changed = True
    else:
        updated = tuple(
            desired if item.meeting_key == desired.meeting_key else item
            for item in proposals
        )
        changed = current != desired

    read_back = next(item for item in updated if item.meeting_key == desired.meeting_key)
    if read_back != desired:
        raise RuntimeError("synthetic read-back did not prove new-time proposal")

    return updated, NewTimeProposalResult(
        meeting_key=desired.meeting_key,
        changed=changed,
        verified=True,
    )


__all__ = [
    "NewTimeProposalResult",
    "SyntheticNewTimeProposal",
    "prepare_new_time_proposal",
]
