"""Synthetic-only Outlook directory and organisation-context reads for OUT-026."""
from __future__ import annotations

from dataclasses import dataclass

from m365_mcp.apps.outlook.mock_ui import OutlookMockFixture
from m365_mcp.apps.outlook.readiness import OutlookReadinessReport

_MAX_DIRECTORY = 250


@dataclass(frozen=True)
class SyntheticDirectoryPerson:
    person_key: str
    display_name: str
    role: str
    org_unit: str
    manager_key: str | None = None

    def __post_init__(self) -> None:
        invalid_person_key = (
            not self.person_key
            or self.person_key != self.person_key.strip()
            or "@" in self.person_key
        )
        if invalid_person_key:
            raise ValueError("person_key must be opaque")
        if self.manager_key is not None and (not self.manager_key or "@" in self.manager_key):
            raise ValueError("manager_key must be opaque")

    def to_projection(self) -> dict[str, object]:
        return {
            "person_key": self.person_key,
            "display_name": self.display_name,
            "role": self.role,
            "org_unit": self.org_unit,
            "manager_key": self.manager_key,
            "synthetic": True,
        }


def default_synthetic_directory() -> tuple[SyntheticDirectoryPerson, ...]:
    return (
        SyntheticDirectoryPerson("dir-lead", "Dana Lead", "Director", "Security"),
        SyntheticDirectoryPerson(
            "dir-architect",
            "Alex Architect",
            "Architect",
            "Security",
            "dir-lead",
        ),
        SyntheticDirectoryPerson(
            "dir-engineer",
            "Evan Engineer",
            "Engineer",
            "Platform",
            "dir-lead",
        ),
    )


def _gate(fixture: OutlookMockFixture, readiness: OutlookReadinessReport) -> None:
    if not fixture.synthetic:
        raise ValueError("OUT-026 fixture execution requires synthetic=true")
    if not readiness.ready_for_readonly_discovery:
        raise ValueError("Outlook read-only discovery is not ready")


def _catalog(
    directory: tuple[SyntheticDirectoryPerson, ...] | None,
) -> tuple[SyntheticDirectoryPerson, ...]:
    catalog = default_synthetic_directory() if directory is None else directory
    if not catalog or len(catalog) > _MAX_DIRECTORY:
        raise ValueError("directory catalog must be non-empty and bounded")
    keys = {item.person_key for item in catalog}
    if len(keys) != len(catalog):
        raise ValueError("directory person keys must be unique")
    if any(item.manager_key is not None and item.manager_key not in keys for item in catalog):
        raise ValueError("manager_key must reference the synthetic directory")
    return catalog


def search_fixture_directory(
    fixture: OutlookMockFixture,
    query: str,
    *,
    readiness: OutlookReadinessReport,
    directory: tuple[SyntheticDirectoryPerson, ...] | None = None,
) -> tuple[SyntheticDirectoryPerson, ...]:
    _gate(fixture, readiness)
    if not query or query != query.strip() or len(query) > 80:
        raise ValueError("query must be non-empty, trimmed and bounded")
    needle = query.casefold()
    return tuple(
        item
        for item in _catalog(directory)
        if needle in item.display_name.casefold()
        or needle in item.role.casefold()
        or needle in item.org_unit.casefold()
    )


def read_fixture_org_context(
    fixture: OutlookMockFixture,
    person_key: str,
    *,
    readiness: OutlookReadinessReport,
    directory: tuple[SyntheticDirectoryPerson, ...] | None = None,
) -> dict[str, object]:
    _gate(fixture, readiness)
    catalog = _catalog(directory)
    match = next((item for item in catalog if item.person_key == person_key), None)
    if match is None:
        raise ValueError("synthetic person_key not found")
    direct_reports = tuple(
        sorted(item.person_key for item in catalog if item.manager_key == person_key)
    )
    return {
        "person": match.to_projection(),
        "direct_report_keys": direct_reports,
        "synthetic": True,
    }


__all__ = [
    "SyntheticDirectoryPerson",
    "default_synthetic_directory",
    "read_fixture_org_context",
    "search_fixture_directory",
]
