"""Read-only M365 Group calendar/mail interaction review for OUT-138."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from m365_mcp.apps.outlook.m365_group_reads import SyntheticM365Group
from m365_mcp.apps.outlook.readiness import OutlookReadinessReport


class GroupSurfaceStatus(StrEnum):
    READ_ONLY_SYNTHETIC = "READ_ONLY_SYNTHETIC"
    NOT_AVAILABLE = "NOT_AVAILABLE"


@dataclass(frozen=True)
class GroupInteractionReview:
    group_key: str
    calendar_status: GroupSurfaceStatus
    mail_status: GroupSurfaceStatus
    membership_mutation_available: bool = False
    generic_executor_available: bool = False
    synthetic: bool = True
    live_support_state: str = "UNOBSERVED"

    def __post_init__(self) -> None:
        if self.membership_mutation_available or self.generic_executor_available:
            raise ValueError("OUT-138 review must not expose mutation or generic execution")
        if not self.synthetic or self.live_support_state != "UNOBSERVED":
            raise ValueError("group interaction review must remain synthetic and live-unobserved")

    def to_projection(self) -> dict[str, object]:
        return {
            "group_key": self.group_key,
            "calendar_status": self.calendar_status.value,
            "mail_status": self.mail_status.value,
            "membership_mutation_available": False,
            "generic_executor_available": False,
            "synthetic": True,
            "live_support_state": self.live_support_state,
        }


def review_group_calendar_mail_interactions(
    group: SyntheticM365Group,
    *,
    readiness: OutlookReadinessReport,
) -> GroupInteractionReview:
    """Review only the synthetic capability shape of group calendar/mail surfaces."""
    if not readiness.ready_for_readonly_discovery:
        raise ValueError("Outlook read-only discovery is not ready")
    if not group.synthetic or group.live_support_state != "UNOBSERVED":
        raise ValueError("synthetic group evidence is required")
    calendar_status = (
        GroupSurfaceStatus.READ_ONLY_SYNTHETIC
        if group.calendar_available
        else GroupSurfaceStatus.NOT_AVAILABLE
    )
    mail_status = (
        GroupSurfaceStatus.READ_ONLY_SYNTHETIC
        if group.mailbox_available
        else GroupSurfaceStatus.NOT_AVAILABLE
    )
    return GroupInteractionReview(group.group_key, calendar_status, mail_status)


__all__ = [
    "GroupInteractionReview",
    "GroupSurfaceStatus",
    "review_group_calendar_mail_interactions",
]
