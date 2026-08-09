"""Synthetic-only Outlook people/contact reads for OUT-025."""
from __future__ import annotations

from dataclasses import dataclass

from m365_mcp.apps.outlook.mock_ui import OutlookMockFixture
from m365_mcp.apps.outlook.readiness import OutlookReadinessReport

_MAX_CONTACTS = 200
_MAX_QUERY = 80


@dataclass(frozen=True)
class SyntheticContact:
    contact_key: str
    display_name: str
    organization: str = ""
    job_title: str = ""

    def __post_init__(self) -> None:
        invalid_contact_key = (
            not self.contact_key
            or self.contact_key != self.contact_key.strip()
            or "@" in self.contact_key
        )
        if invalid_contact_key:
            raise ValueError("contact_key must be an opaque semantic token")
        if not self.display_name or self.display_name != self.display_name.strip():
            raise ValueError("display_name must be non-empty and trimmed")

    def to_projection(self) -> dict[str, object]:
        return {
            "contact_key": self.contact_key,
            "display_name": self.display_name,
            "organization": self.organization,
            "job_title": self.job_title,
            "synthetic": True,
        }


@dataclass(frozen=True)
class ContactSearchResult:
    items: tuple[SyntheticContact, ...]
    total_matching: int
    synthetic: bool = True


def default_synthetic_contacts() -> tuple[SyntheticContact, ...]:
    return (
        SyntheticContact("person-alpha", "Alex Example", "Example Org", "Architect"),
        SyntheticContact("person-bravo", "Bea Sample", "Sample Org", "Engineer"),
        SyntheticContact("person-charlie", "Chris Demo", "Example Org", "Manager"),
    )


def _catalog(contacts: tuple[SyntheticContact, ...] | None) -> tuple[SyntheticContact, ...]:
    catalog = default_synthetic_contacts() if contacts is None else contacts
    if not catalog or len(catalog) > _MAX_CONTACTS:
        raise ValueError("contact catalog must be non-empty and bounded")
    keys = tuple(item.contact_key for item in catalog)
    if len(set(keys)) != len(keys):
        raise ValueError("contact keys must be unique")
    return catalog


def _gate(fixture: OutlookMockFixture, readiness: OutlookReadinessReport) -> None:
    if not fixture.synthetic:
        raise ValueError("OUT-025 fixture execution requires synthetic=true")
    if not readiness.ready_for_readonly_discovery:
        raise ValueError("Outlook read-only discovery is not ready")


def search_fixture_contacts(
    fixture: OutlookMockFixture,
    query: str,
    *,
    readiness: OutlookReadinessReport,
    contacts: tuple[SyntheticContact, ...] | None = None,
) -> ContactSearchResult:
    _gate(fixture, readiness)
    if not query or query != query.strip() or len(query) > _MAX_QUERY:
        raise ValueError("query must be non-empty, trimmed and bounded")
    needle = query.casefold()
    matches = tuple(
        item
        for item in _catalog(contacts)
        if needle in item.display_name.casefold()
        or needle in item.organization.casefold()
        or needle in item.job_title.casefold()
    )
    return ContactSearchResult(matches, len(matches))


def get_fixture_contact(
    fixture: OutlookMockFixture,
    contact_key: str,
    *,
    readiness: OutlookReadinessReport,
    contacts: tuple[SyntheticContact, ...] | None = None,
) -> SyntheticContact:
    _gate(fixture, readiness)
    if not contact_key or contact_key != contact_key.strip() or "@" in contact_key:
        raise ValueError("contact_key must be an opaque semantic token")
    match = next(
        (item for item in _catalog(contacts) if item.contact_key == contact_key),
        None,
    )
    if match is None:
        raise ValueError("synthetic contact_key not found")
    return match


__all__ = [
    "ContactSearchResult",
    "SyntheticContact",
    "default_synthetic_contacts",
    "get_fixture_contact",
    "search_fixture_contacts",
]
