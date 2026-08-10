"""Synthetic M365 Group discovery/read models for OUT-137."""

from __future__ import annotations

from dataclasses import dataclass

from m365_mcp.apps.outlook.readiness import OutlookReadinessReport

_MAX_GROUPS = 100


def _key(field: str, value: str) -> str:
    if not value or value != value.strip() or any(char.isspace() for char in value):
        raise ValueError(f"{field} must be a non-empty semantic token")
    if "@" in value or "://" in value or "/" in value:
        raise ValueError(f"{field} must not encode an address or URL")
    return value


@dataclass(frozen=True)
class SyntheticM365Group:
    group_key: str
    display_name: str
    calendar_available: bool
    mailbox_available: bool
    membership_governance_state: str = "OUT_OF_SCOPE"
    synthetic: bool = True
    live_support_state: str = "UNOBSERVED"

    def __post_init__(self) -> None:
        _key("group_key", self.group_key)
        if not self.display_name or self.display_name != self.display_name.strip():
            raise ValueError("display_name must be non-empty and trimmed")
        if len(self.display_name) > 120:
            raise ValueError("display_name exceeds bounded size")
        if self.membership_governance_state != "OUT_OF_SCOPE":
            raise ValueError("OUT-137 must not imply group membership governance")
        if not self.synthetic or self.live_support_state != "UNOBSERVED":
            raise ValueError("M365 Group reads must remain synthetic and live-unobserved")

    def to_projection(self) -> dict[str, object]:
        return {
            "group_key": self.group_key,
            "display_name": self.display_name,
            "calendar_available": self.calendar_available,
            "mailbox_available": self.mailbox_available,
            "membership_governance_state": self.membership_governance_state,
            "synthetic": True,
            "live_support_state": self.live_support_state,
        }


def default_synthetic_groups() -> tuple[SyntheticM365Group, ...]:
    return (
        SyntheticM365Group("group-alpha", "Synthetic Project Group", True, True),
        SyntheticM365Group("group-beta", "Synthetic Read Group", False, True),
    )


def list_synthetic_groups(
    groups: tuple[SyntheticM365Group, ...],
    *,
    readiness: OutlookReadinessReport,
) -> tuple[SyntheticM365Group, ...]:
    if not readiness.ready_for_readonly_discovery:
        raise ValueError("Outlook read-only discovery is not ready")
    if len(groups) > _MAX_GROUPS:
        raise ValueError("group catalog exceeds bounded size")
    keys = tuple(group.group_key for group in groups)
    if len(keys) != len(set(keys)):
        raise ValueError("group catalog contains duplicate group_key")
    return tuple(sorted(groups, key=lambda item: item.group_key))


def get_synthetic_group(
    groups: tuple[SyntheticM365Group, ...],
    group_key: str,
    *,
    readiness: OutlookReadinessReport,
) -> SyntheticM365Group:
    _key("group_key", group_key)
    catalog = list_synthetic_groups(groups, readiness=readiness)
    matches = tuple(item for item in catalog if item.group_key == group_key)
    if len(matches) != 1:
        raise ValueError("synthetic group_key must resolve exactly once")
    return matches[0]


__all__ = [
    "SyntheticM365Group",
    "default_synthetic_groups",
    "get_synthetic_group",
    "list_synthetic_groups",
]
