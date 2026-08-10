"""Read-only M365 Group calendar/mail interaction review for OUT-138."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from m365_mcp.apps.outlook.readiness import OutlookReadinessReport


class GroupSurfaceStatus(StrEnum):
    READ_ONLY_SYNTHETIC = "READ_ONLY_SYNTHETIC"
    NOT_AVAILABLE = "NOT_AVAILABLE"


@dataclass(frozen=True)
class GroupInteractionReviewInput:
    group_key: str
    calendar_available: bool
    mailbox_available: bool
    synthetic: bool = True
    live_support_state: str = "UNOBSERVED"

    def __post_init__(self) -> None:
        if (
            not self.group_key
            or self.group_key != self.group_key.strip()
            or any(char.isspace() for char in self.group_key)
        ):
            raise ValueError("group_key must be a non-empty semantic token")
        if "@" in self.group_key or "://" in self.group_key or "/" in self.group_key:
            raise ValueError("group_key must not encode an address or URL")
        if not self.synthetic or self.live_support_state != "UNOBSERVED":
            raise ValueError("group review input must remain synthetic and live-unobserved")


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
    group: GroupInteractionReviewInput,
    *,
    readiness: OutlookReadinessReport,
) -> GroupInteractionReview:
    """Review only the synthetic capability shape of group calendar/mail surfaces."""
    if not readiness.ready_for_readonly_discovery:
        raise ValueError("Outlook read-only discovery is not ready")
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
    "GroupInteractionReviewInput",
    "GroupSurfaceStatus",
    "review_group_calendar_mail_interactions",
]
