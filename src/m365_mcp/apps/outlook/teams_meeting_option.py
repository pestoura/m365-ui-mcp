"""Tenant-neutral synthetic Teams meeting desired-state option for OUT-083."""

from __future__ import annotations

from dataclasses import dataclass

from m365_mcp.apps.outlook.readiness import OutlookReadinessReport


@dataclass(frozen=True)
class SyntheticTeamsMeetingOption:
    meeting_key: str
    enabled: bool

    def __post_init__(self) -> None:
        _validate_key(self.meeting_key)
        if not isinstance(self.enabled, bool):
            raise ValueError("enabled must be a boolean")

    def to_payload(self) -> dict[str, object]:
        return {"meeting_key": self.meeting_key, "enabled": self.enabled}


@dataclass(frozen=True)
class TeamsMeetingOptionResult:
    meeting_key: str
    enabled: bool
    changed: bool
    verified: bool
    join_url_generated: bool = False
    synthetic: bool = True


def _validate_key(value: str) -> None:
    if not value or value != value.strip() or any(char.isspace() for char in value):
        raise ValueError("meeting_key must be a non-empty semantic token")


def set_teams_meeting_option(
    options: tuple[SyntheticTeamsMeetingOption, ...],
    desired: SyntheticTeamsMeetingOption,
    *,
    readiness: OutlookReadinessReport,
) -> tuple[tuple[SyntheticTeamsMeetingOption, ...], TeamsMeetingOptionResult]:
    """Set synthetic Teams-meeting intent without generating a live join URL."""
    if not readiness.ready_for_readonly_discovery:
        raise ValueError("Outlook read-only discovery is not ready")
    keys = tuple(item.meeting_key for item in options)
    if len(keys) != len(set(keys)):
        raise ValueError("Teams option catalog contains duplicate meeting_key values")

    current = next((item for item in options if item.meeting_key == desired.meeting_key), None)
    if current is None:
        updated = (*options, desired)
        changed = True
    else:
        updated = tuple(
            desired if item.meeting_key == desired.meeting_key else item for item in options
        )
        changed = current != desired

    read_back = next(item for item in updated if item.meeting_key == desired.meeting_key)
    if read_back != desired:
        raise RuntimeError("synthetic read-back did not prove Teams meeting option")

    return updated, TeamsMeetingOptionResult(
        meeting_key=desired.meeting_key,
        enabled=desired.enabled,
        changed=changed,
        verified=True,
    )


__all__ = [
    "SyntheticTeamsMeetingOption",
    "TeamsMeetingOptionResult",
    "set_teams_meeting_option",
]
