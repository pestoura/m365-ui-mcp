"""Synthetic-only shared-calendar membership state for OUT-095.

Membership uses opaque calendar/member keys and purely functional local state.
No mailbox identity, address, URL, selector, session, token or live Microsoft 365
mutation is represented.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from m365_mcp.apps.outlook.readiness import OutlookReadinessReport

_MAX_MEMBERS = 200


class MembershipAction(StrEnum):
    """Closed synthetic membership mutations."""

    ADD = "ADD"
    REMOVE = "REMOVE"


def _validate_key(field_name: str, value: str) -> None:
    invalid = (
        not value
        or value != value.strip()
        or any(char.isspace() for char in value)
    )
    if invalid:
        raise ValueError(f"{field_name} must be a non-empty semantic token")
    if "@" in value:
        raise ValueError(f"{field_name} must not encode an address identity")


@dataclass(frozen=True)
class SharedCalendarMember:
    """One synthetic calendar/member relation."""

    calendar_key: str
    member_key: str

    def __post_init__(self) -> None:
        _validate_key("calendar_key", self.calendar_key)
        _validate_key("member_key", self.member_key)


@dataclass(frozen=True)
class MembershipRequest:
    """One local membership mutation request."""

    action: MembershipAction
    calendar_key: str
    member_key: str

    def __post_init__(self) -> None:
        if not isinstance(self.action, MembershipAction):
            raise ValueError("action must be a closed MembershipAction")
        _validate_key("calendar_key", self.calendar_key)
        _validate_key("member_key", self.member_key)


@dataclass(frozen=True)
class MembershipState:
    """Deterministic read-side membership projection."""

    calendar_key: str
    member_keys: tuple[str, ...]
    member_count: int
    synthetic: bool

    def to_projection(self) -> dict[str, object]:
        return {
            "calendar_key": self.calendar_key,
            "member_keys": list(self.member_keys),
            "member_count": self.member_count,
            "synthetic": self.synthetic,
        }


@dataclass(frozen=True)
class MembershipResult:
    """Read-back proof for a synthetic add/remove."""

    action: MembershipAction
    calendar_key: str
    member_key: str
    previous_is_member: bool
    read_back_is_member: bool
    changed: bool
    verified: bool
    synthetic: bool


def _require_ready(readiness: OutlookReadinessReport) -> None:
    if not readiness.ready_for_readonly_discovery:
        raise ValueError("Outlook read-only discovery is not ready")


def _validate_members(members: tuple[SharedCalendarMember, ...]) -> None:
    if len(members) > _MAX_MEMBERS:
        raise ValueError("shared calendar members exceed bounded size")
    pairs = tuple((item.calendar_key, item.member_key) for item in members)
    if len(set(pairs)) != len(pairs):
        raise ValueError("shared calendar members contain duplicate relation")


def read_shared_calendar_membership(
    members: tuple[SharedCalendarMember, ...],
    *,
    calendar_key: str,
    readiness: OutlookReadinessReport,
) -> MembershipState:
    """Read one calendar's bounded synthetic membership."""
    _require_ready(readiness)
    _validate_key("calendar_key", calendar_key)
    _validate_members(members)
    keys = tuple(
        sorted(item.member_key for item in members if item.calendar_key == calendar_key)
    )
    return MembershipState(
        calendar_key=calendar_key,
        member_keys=keys,
        member_count=len(keys),
        synthetic=True,
    )


def apply_shared_calendar_membership(
    members: tuple[SharedCalendarMember, ...],
    request: MembershipRequest,
    *,
    readiness: OutlookReadinessReport,
) -> tuple[tuple[SharedCalendarMember, ...], MembershipResult]:
    """Apply one synthetic membership mutation and prove it by read-back."""
    _require_ready(readiness)
    _validate_members(members)
    relation = SharedCalendarMember(request.calendar_key, request.member_key)
    previous = relation in members

    if request.action is MembershipAction.ADD:
        if previous:
            updated = members
            changed = False
        else:
            if len(members) >= _MAX_MEMBERS:
                raise ValueError("shared calendar members exceed bounded size")
            updated = members + (relation,)
            changed = True
        expected = True
    elif request.action is MembershipAction.REMOVE:
        updated = tuple(item for item in members if item != relation)
        changed = previous
        expected = False
    else:
        raise ValueError("unsupported membership action")

    updated = tuple(sorted(updated, key=lambda item: (item.calendar_key, item.member_key)))
    read_back = read_shared_calendar_membership(
        updated,
        calendar_key=request.calendar_key,
        readiness=readiness,
    )
    observed = request.member_key in read_back.member_keys
    if observed is not expected:
        raise RuntimeError("shared calendar membership read-back did not prove requested state")
    return updated, MembershipResult(
        action=request.action,
        calendar_key=request.calendar_key,
        member_key=request.member_key,
        previous_is_member=previous,
        read_back_is_member=observed,
        changed=changed,
        verified=True,
        synthetic=True,
    )


__all__ = [
    "MembershipAction",
    "MembershipRequest",
    "MembershipResult",
    "MembershipState",
    "SharedCalendarMember",
    "apply_shared_calendar_membership",
    "read_shared_calendar_membership",
]
