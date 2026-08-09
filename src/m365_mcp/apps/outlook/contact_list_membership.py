"""Synthetic-only Outlook contact-list membership for OUT-103.

Membership uses opaque contact/list keys and pure local state. No address,
mailbox identity, URL, selector, session, token or live Microsoft 365 material
is represented.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from m365_mcp.apps.outlook.contact_list_reads import SyntheticContactList
from m365_mcp.apps.outlook.mock_ui import OutlookMockFixture
from m365_mcp.apps.outlook.people_reads import SyntheticContact
from m365_mcp.apps.outlook.readiness import OutlookReadinessReport

_MAX_MEMBERS_PER_LIST = 200


class ContactListMembershipAction(StrEnum):
    ADD = "ADD"
    REMOVE = "REMOVE"


def _validate_key(field_name: str, value: str) -> None:
    if (
        not value
        or value != value.strip()
        or "@" in value
        or any(char.isspace() for char in value)
    ):
        raise ValueError(f"{field_name} must be an opaque semantic token")


@dataclass(frozen=True)
class ContactListMembershipRequest:
    action: ContactListMembershipAction
    list_key: str
    contact_key: str

    def __post_init__(self) -> None:
        if not isinstance(self.action, ContactListMembershipAction):
            raise ValueError("action must be a closed ContactListMembershipAction")
        _validate_key("list_key", self.list_key)
        _validate_key("contact_key", self.contact_key)


@dataclass(frozen=True)
class ContactListMembershipResult:
    action: ContactListMembershipAction
    list_key: str
    contact_key: str
    previous_is_member: bool
    read_back_is_member: bool
    changed: bool
    member_count: int
    verified: bool
    synthetic: bool


def _gate(fixture: OutlookMockFixture, readiness: OutlookReadinessReport) -> None:
    if not fixture.synthetic:
        raise ValueError("OUT-103 fixture execution requires synthetic=true")
    if not readiness.ready_for_readonly_discovery:
        raise ValueError("Outlook read-only discovery is not ready")


def _require_contact(contacts: tuple[SyntheticContact, ...], contact_key: str) -> None:
    keys = tuple(item.contact_key for item in contacts)
    if len(set(keys)) != len(keys):
        raise ValueError("contact keys must be unique")
    if contact_key not in keys:
        raise ValueError("synthetic contact_key not found")


def apply_contact_list_membership(
    fixture: OutlookMockFixture,
    contacts: tuple[SyntheticContact, ...],
    lists: tuple[SyntheticContactList, ...],
    request: ContactListMembershipRequest,
    *,
    readiness: OutlookReadinessReport,
) -> tuple[tuple[SyntheticContactList, ...], ContactListMembershipResult]:
    """Apply one idempotent membership change and prove state by read-back."""
    _gate(fixture, readiness)
    _require_contact(contacts, request.contact_key)
    list_keys = tuple(item.list_key for item in lists)
    if len(set(list_keys)) != len(list_keys):
        raise ValueError("contact-list keys must be unique")
    existing = next((item for item in lists if item.list_key == request.list_key), None)
    if existing is None:
        raise ValueError("synthetic list_key not found")
    if len(existing.member_keys) > _MAX_MEMBERS_PER_LIST:
        raise ValueError("contact-list members exceed bounded size")

    previous = request.contact_key in existing.member_keys
    if request.action is ContactListMembershipAction.ADD:
        if previous:
            members = existing.member_keys
            changed = False
        else:
            if len(existing.member_keys) >= _MAX_MEMBERS_PER_LIST:
                raise ValueError("contact-list members exceed bounded size")
            members = existing.member_keys + (request.contact_key,)
            changed = True
        expected = True
    elif request.action is ContactListMembershipAction.REMOVE:
        members = tuple(
            key for key in existing.member_keys if key != request.contact_key
        )
        changed = previous
        expected = False
    else:
        raise ValueError("unsupported contact-list membership action")

    desired = SyntheticContactList(
        existing.list_key,
        existing.display_name,
        tuple(sorted(members)),
    )
    updated = tuple(
        sorted(
            (desired if item.list_key == request.list_key else item for item in lists),
            key=lambda item: item.list_key,
        )
    )
    read_back = next(item for item in updated if item.list_key == request.list_key)
    observed = request.contact_key in read_back.member_keys
    if observed is not expected:
        raise RuntimeError("contact-list membership read-back did not prove requested state")
    return updated, ContactListMembershipResult(
        action=request.action,
        list_key=request.list_key,
        contact_key=request.contact_key,
        previous_is_member=previous,
        read_back_is_member=observed,
        changed=changed,
        member_count=len(read_back.member_keys),
        verified=True,
        synthetic=True,
    )


__all__ = [
    "ContactListMembershipAction",
    "ContactListMembershipRequest",
    "ContactListMembershipResult",
    "apply_contact_list_membership",
]
