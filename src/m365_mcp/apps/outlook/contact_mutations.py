"""Synthetic-only Outlook contact mutations for OUT-100.

Contacts reuse the bounded OUT-025 semantic model. Mutations are pure local
state transformations with deterministic read-back and no address, mailbox,
URL, selector, session, token or live Microsoft 365 material.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from m365_mcp.apps.outlook.mock_ui import OutlookMockFixture
from m365_mcp.apps.outlook.people_reads import SyntheticContact
from m365_mcp.apps.outlook.readiness import OutlookReadinessReport

_MAX_CONTACTS = 200


class ContactAction(StrEnum):
    CREATE = "CREATE"
    UPDATE = "UPDATE"
    DELETE = "DELETE"


def _validate_key(value: str) -> None:
    if not value or value != value.strip() or "@" in value or any(
        char.isspace() for char in value
    ):
        raise ValueError("contact_key must be an opaque semantic token")


@dataclass(frozen=True)
class ContactMutationRequest:
    action: ContactAction
    contact_key: str
    display_name: str | None = None
    organization: str = ""
    job_title: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.action, ContactAction):
            raise ValueError("action must be a closed ContactAction")
        _validate_key(self.contact_key)
        if self.action in (ContactAction.CREATE, ContactAction.UPDATE):
            if not self.display_name or self.display_name != self.display_name.strip():
                raise ValueError("create/update requires a non-empty trimmed display_name")


@dataclass(frozen=True)
class ContactMutationResult:
    action: ContactAction
    contact_key: str
    existed_before: bool
    exists_after: bool
    changed: bool
    read_back: SyntheticContact | None
    verified: bool
    synthetic: bool


def _gate(fixture: OutlookMockFixture, readiness: OutlookReadinessReport) -> None:
    if not fixture.synthetic:
        raise ValueError("OUT-100 fixture execution requires synthetic=true")
    if not readiness.ready_for_readonly_discovery:
        raise ValueError("Outlook read-only discovery is not ready")


def _validate_catalog(contacts: tuple[SyntheticContact, ...]) -> None:
    if len(contacts) > _MAX_CONTACTS:
        raise ValueError("contact catalog exceeds bounded size")
    keys = tuple(item.contact_key for item in contacts)
    if len(set(keys)) != len(keys):
        raise ValueError("contact keys must be unique")


def apply_contact_mutation(
    fixture: OutlookMockFixture,
    contacts: tuple[SyntheticContact, ...],
    request: ContactMutationRequest,
    *,
    readiness: OutlookReadinessReport,
) -> tuple[tuple[SyntheticContact, ...], ContactMutationResult]:
    """Apply one bounded contact mutation and prove the resulting local state."""
    _gate(fixture, readiness)
    _validate_catalog(contacts)
    existing = next(
        (item for item in contacts if item.contact_key == request.contact_key),
        None,
    )

    if request.action is ContactAction.CREATE:
        desired = SyntheticContact(
            request.contact_key,
            request.display_name or "",
            request.organization,
            request.job_title,
        )
        if existing is None:
            if len(contacts) >= _MAX_CONTACTS:
                raise ValueError("contact catalog exceeds bounded size")
            updated = contacts + (desired,)
            changed = True
        elif existing == desired:
            updated = contacts
            changed = False
        else:
            raise ValueError("contact_key already exists with different state")
        expected: SyntheticContact | None = desired
    elif request.action is ContactAction.UPDATE:
        if existing is None:
            raise ValueError("synthetic contact_key not found")
        desired = SyntheticContact(
            request.contact_key,
            request.display_name or "",
            request.organization,
            request.job_title,
        )
        updated = tuple(
            desired if item.contact_key == request.contact_key else item
            for item in contacts
        )
        changed = desired != existing
        expected = desired
    elif request.action is ContactAction.DELETE:
        updated = tuple(
            item for item in contacts if item.contact_key != request.contact_key
        )
        changed = existing is not None
        expected = None
    else:
        raise ValueError("unsupported contact mutation")

    updated = tuple(sorted(updated, key=lambda item: item.contact_key))
    _validate_catalog(updated)
    read_back = next(
        (item for item in updated if item.contact_key == request.contact_key),
        None,
    )
    if read_back != expected:
        raise RuntimeError("contact read-back did not prove requested state")
    return updated, ContactMutationResult(
        action=request.action,
        contact_key=request.contact_key,
        existed_before=existing is not None,
        exists_after=read_back is not None,
        changed=changed,
        read_back=read_back,
        verified=True,
        synthetic=True,
    )


__all__ = [
    "ContactAction",
    "ContactMutationRequest",
    "ContactMutationResult",
    "apply_contact_mutation",
]
