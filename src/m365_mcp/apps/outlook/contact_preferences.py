"""Synthetic-only Outlook contact categories/favorites for OUT-101.

Preferences reference opaque contact/category keys only and remain local state.
No address, mailbox identity, URL, selector, session material, token or live
Microsoft 365 mutation is represented.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from m365_mcp.apps.outlook.mock_ui import OutlookMockFixture
from m365_mcp.apps.outlook.people_reads import SyntheticContact
from m365_mcp.apps.outlook.readiness import OutlookReadinessReport

_MAX_PREFERENCES = 200
_MAX_CATEGORIES = 20


class ContactPreferenceAction(StrEnum):
    SET_CATEGORIES = "SET_CATEGORIES"
    SET_FAVORITE = "SET_FAVORITE"


def _validate_key(field_name: str, value: str) -> None:
    if (
        not value
        or value != value.strip()
        or "@" in value
        or any(char.isspace() for char in value)
    ):
        raise ValueError(f"{field_name} must be an opaque semantic token")


@dataclass(frozen=True)
class ContactPreference:
    contact_key: str
    category_keys: tuple[str, ...] = ()
    favorite: bool = False

    def __post_init__(self) -> None:
        _validate_key("contact_key", self.contact_key)
        if len(self.category_keys) > _MAX_CATEGORIES:
            raise ValueError("contact categories exceed bounded size")
        if len(set(self.category_keys)) != len(self.category_keys):
            raise ValueError("contact categories must be unique")
        for key in self.category_keys:
            _validate_key("category_key", key)

    def to_projection(self) -> dict[str, object]:
        return {
            "contact_key": self.contact_key,
            "category_keys": list(self.category_keys),
            "favorite": self.favorite,
            "synthetic": True,
        }


@dataclass(frozen=True)
class ContactPreferenceRequest:
    action: ContactPreferenceAction
    contact_key: str
    category_keys: tuple[str, ...] = ()
    favorite: bool | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.action, ContactPreferenceAction):
            raise ValueError("action must be a closed ContactPreferenceAction")
        _validate_key("contact_key", self.contact_key)
        if self.action is ContactPreferenceAction.SET_CATEGORIES:
            ContactPreference(self.contact_key, self.category_keys, False)
        elif self.favorite is None:
            raise ValueError("SET_FAVORITE requires favorite")


@dataclass(frozen=True)
class ContactPreferenceResult:
    action: ContactPreferenceAction
    contact_key: str
    previous: ContactPreference
    read_back: ContactPreference
    changed: bool
    verified: bool
    synthetic: bool


def _gate(fixture: OutlookMockFixture, readiness: OutlookReadinessReport) -> None:
    if not fixture.synthetic:
        raise ValueError("OUT-101 fixture execution requires synthetic=true")
    if not readiness.ready_for_readonly_discovery:
        raise ValueError("Outlook read-only discovery is not ready")


def _validate_state(preferences: tuple[ContactPreference, ...]) -> None:
    if len(preferences) > _MAX_PREFERENCES:
        raise ValueError("contact preferences exceed bounded size")
    keys = tuple(item.contact_key for item in preferences)
    if len(set(keys)) != len(keys):
        raise ValueError("contact preferences contain duplicate contact_key")


def _require_contact(
    contacts: tuple[SyntheticContact, ...], contact_key: str
) -> None:
    keys = tuple(item.contact_key for item in contacts)
    if len(set(keys)) != len(keys):
        raise ValueError("contact keys must be unique")
    if contact_key not in keys:
        raise ValueError("synthetic contact_key not found")


def read_contact_preference(
    fixture: OutlookMockFixture,
    preferences: tuple[ContactPreference, ...],
    *,
    contact_key: str,
    readiness: OutlookReadinessReport,
) -> ContactPreference:
    _gate(fixture, readiness)
    _validate_key("contact_key", contact_key)
    _validate_state(preferences)
    return next(
        (item for item in preferences if item.contact_key == contact_key),
        ContactPreference(contact_key),
    )


def apply_contact_preference(
    fixture: OutlookMockFixture,
    contacts: tuple[SyntheticContact, ...],
    preferences: tuple[ContactPreference, ...],
    request: ContactPreferenceRequest,
    *,
    readiness: OutlookReadinessReport,
) -> tuple[tuple[ContactPreference, ...], ContactPreferenceResult]:
    """Apply one bounded preference mutation and prove exact state by read-back."""
    _gate(fixture, readiness)
    _validate_state(preferences)
    _require_contact(contacts, request.contact_key)
    previous = read_contact_preference(
        fixture,
        preferences,
        contact_key=request.contact_key,
        readiness=readiness,
    )

    if request.action is ContactPreferenceAction.SET_CATEGORIES:
        desired = ContactPreference(
            request.contact_key,
            tuple(sorted(request.category_keys)),
            previous.favorite,
        )
    elif request.action is ContactPreferenceAction.SET_FAVORITE:
        desired = ContactPreference(
            request.contact_key,
            previous.category_keys,
            bool(request.favorite),
        )
    else:
        raise ValueError("unsupported contact preference action")

    remaining = tuple(
        item for item in preferences if item.contact_key != request.contact_key
    )
    if previous == ContactPreference(request.contact_key) and desired == previous:
        updated = preferences
    else:
        if not any(item.contact_key == request.contact_key for item in preferences):
            if len(preferences) >= _MAX_PREFERENCES:
                raise ValueError("contact preferences exceed bounded size")
        updated = remaining + (desired,)
    updated = tuple(sorted(updated, key=lambda item: item.contact_key))
    read_back = read_contact_preference(
        fixture,
        updated,
        contact_key=request.contact_key,
        readiness=readiness,
    )
    if read_back != desired:
        raise RuntimeError("contact preference read-back did not prove requested state")
    return updated, ContactPreferenceResult(
        action=request.action,
        contact_key=request.contact_key,
        previous=previous,
        read_back=read_back,
        changed=previous != desired,
        verified=True,
        synthetic=True,
    )


__all__ = [
    "ContactPreference",
    "ContactPreferenceAction",
    "ContactPreferenceRequest",
    "ContactPreferenceResult",
    "apply_contact_preference",
    "read_contact_preference",
]
