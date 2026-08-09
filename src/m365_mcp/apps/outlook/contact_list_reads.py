"""Synthetic-only Outlook contact-list reads for OUT-027."""
from __future__ import annotations

from dataclasses import dataclass

from m365_mcp.apps.outlook.mock_ui import OutlookMockFixture
from m365_mcp.apps.outlook.readiness import OutlookReadinessReport

_MAX_LISTS = 50


@dataclass(frozen=True)
class SyntheticContactList:
    list_key: str
    display_name: str
    member_keys: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.list_key or self.list_key != self.list_key.strip() or "@" in self.list_key:
            raise ValueError("list_key must be opaque")
        if not self.display_name or self.display_name != self.display_name.strip():
            raise ValueError("display_name must be non-empty and trimmed")
        if len(set(self.member_keys)) != len(self.member_keys):
            raise ValueError("contact-list members must be unique")
        if any(not key or "@" in key for key in self.member_keys):
            raise ValueError("member keys must be opaque")

    def to_projection(self) -> dict[str, object]:
        return {"list_key": self.list_key, "display_name": self.display_name, "member_keys": self.member_keys, "member_count": len(self.member_keys), "synthetic": True}


def default_synthetic_contact_lists() -> tuple[SyntheticContactList, ...]:
    return (
        SyntheticContactList("list-security", "Security Contacts", ("person-alpha", "person-charlie")),
        SyntheticContactList("list-platform", "Platform Contacts", ("person-bravo",)),
    )


def _gate(fixture: OutlookMockFixture, readiness: OutlookReadinessReport) -> None:
    if not fixture.synthetic:
        raise ValueError("OUT-027 fixture execution requires synthetic=true")
    if not readiness.ready_for_readonly_discovery:
        raise ValueError("Outlook read-only discovery is not ready")


def _catalog(lists: tuple[SyntheticContactList, ...] | None) -> tuple[SyntheticContactList, ...]:
    catalog = default_synthetic_contact_lists() if lists is None else lists
    if not catalog or len(catalog) > _MAX_LISTS:
        raise ValueError("contact-list catalog must be non-empty and bounded")
    keys = tuple(item.list_key for item in catalog)
    if len(set(keys)) != len(keys):
        raise ValueError("contact-list keys must be unique")
    return catalog


def list_fixture_contact_lists(fixture: OutlookMockFixture, *, readiness: OutlookReadinessReport, lists: tuple[SyntheticContactList, ...] | None = None) -> tuple[SyntheticContactList, ...]:
    _gate(fixture, readiness)
    return _catalog(lists)


def get_fixture_contact_list(fixture: OutlookMockFixture, list_key: str, *, readiness: OutlookReadinessReport, lists: tuple[SyntheticContactList, ...] | None = None) -> SyntheticContactList:
    _gate(fixture, readiness)
    if not list_key or list_key != list_key.strip() or "@" in list_key:
        raise ValueError("list_key must be opaque")
    match = next((item for item in _catalog(lists) if item.list_key == list_key), None)
    if match is None:
        raise ValueError("synthetic list_key not found")
    return match


__all__ = ["SyntheticContactList", "default_synthetic_contact_lists", "get_fixture_contact_list", "list_fixture_contact_lists"]
