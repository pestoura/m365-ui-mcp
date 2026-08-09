"""Synthetic-only Outlook contact-list mutations for OUT-102.

List state reuses the bounded OUT-027 semantic model. Create/update/delete are
pure local transformations with deterministic read-back and no address, URL,
selector, session, token or live Microsoft 365 material.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from m365_mcp.apps.outlook.contact_list_reads import SyntheticContactList
from m365_mcp.apps.outlook.mock_ui import OutlookMockFixture
from m365_mcp.apps.outlook.readiness import OutlookReadinessReport

_MAX_LISTS = 50


class ContactListAction(StrEnum):
    CREATE = "CREATE"
    UPDATE = "UPDATE"
    DELETE = "DELETE"


def _validate_key(value: str) -> None:
    if not value or value != value.strip() or "@" in value or any(
        char.isspace() for char in value
    ):
        raise ValueError("list_key must be an opaque semantic token")


@dataclass(frozen=True)
class ContactListMutationRequest:
    action: ContactListAction
    list_key: str
    display_name: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.action, ContactListAction):
            raise ValueError("action must be a closed ContactListAction")
        _validate_key(self.list_key)
        if self.action in (ContactListAction.CREATE, ContactListAction.UPDATE):
            if not self.display_name or self.display_name != self.display_name.strip():
                raise ValueError("create/update requires a non-empty trimmed display_name")


@dataclass(frozen=True)
class ContactListMutationResult:
    action: ContactListAction
    list_key: str
    existed_before: bool
    exists_after: bool
    changed: bool
    read_back: SyntheticContactList | None
    verified: bool
    synthetic: bool


def _gate(fixture: OutlookMockFixture, readiness: OutlookReadinessReport) -> None:
    if not fixture.synthetic:
        raise ValueError("OUT-102 fixture execution requires synthetic=true")
    if not readiness.ready_for_readonly_discovery:
        raise ValueError("Outlook read-only discovery is not ready")


def _validate_catalog(lists: tuple[SyntheticContactList, ...]) -> None:
    if len(lists) > _MAX_LISTS:
        raise ValueError("contact-list catalog exceeds bounded size")
    keys = tuple(item.list_key for item in lists)
    if len(set(keys)) != len(keys):
        raise ValueError("contact-list keys must be unique")


def apply_contact_list_mutation(
    fixture: OutlookMockFixture,
    lists: tuple[SyntheticContactList, ...],
    request: ContactListMutationRequest,
    *,
    readiness: OutlookReadinessReport,
) -> tuple[tuple[SyntheticContactList, ...], ContactListMutationResult]:
    """Apply one list mutation and prove resulting local state by read-back."""
    _gate(fixture, readiness)
    _validate_catalog(lists)
    existing = next((item for item in lists if item.list_key == request.list_key), None)

    if request.action is ContactListAction.CREATE:
        desired = SyntheticContactList(request.list_key, request.display_name or "", ())
        if existing is None:
            if len(lists) >= _MAX_LISTS:
                raise ValueError("contact-list catalog exceeds bounded size")
            updated = lists + (desired,)
            changed = True
        elif existing == desired:
            updated = lists
            changed = False
        else:
            raise ValueError("list_key already exists with different state")
        expected: SyntheticContactList | None = desired
    elif request.action is ContactListAction.UPDATE:
        if existing is None:
            raise ValueError("synthetic list_key not found")
        desired = SyntheticContactList(
            request.list_key,
            request.display_name or "",
            existing.member_keys,
        )
        updated = tuple(
            desired if item.list_key == request.list_key else item for item in lists
        )
        changed = desired != existing
        expected = desired
    elif request.action is ContactListAction.DELETE:
        updated = tuple(item for item in lists if item.list_key != request.list_key)
        changed = existing is not None
        expected = None
    else:
        raise ValueError("unsupported contact-list mutation")

    updated = tuple(sorted(updated, key=lambda item: item.list_key))
    _validate_catalog(updated)
    read_back = next((item for item in updated if item.list_key == request.list_key), None)
    if read_back != expected:
        raise RuntimeError("contact-list read-back did not prove requested state")
    return updated, ContactListMutationResult(
        action=request.action,
        list_key=request.list_key,
        existed_before=existing is not None,
        exists_after=read_back is not None,
        changed=changed,
        read_back=read_back,
        verified=True,
        synthetic=True,
    )


__all__ = [
    "ContactListAction",
    "ContactListMutationRequest",
    "ContactListMutationResult",
    "apply_contact_list_mutation",
]
