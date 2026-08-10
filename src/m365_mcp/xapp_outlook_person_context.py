"""Synthetic-only Outlook person context composite for XAPP-022.

The composite links already-produced synthetic contact and directory records.
It never resolves tenant identities, addresses, sessions, or browser state.
"""

from __future__ import annotations

from dataclasses import dataclass

from m365_mcp.apps.outlook.directory_org_reads import SyntheticDirectoryPerson
from m365_mcp.apps.outlook.people_reads import SyntheticContact


@dataclass(frozen=True)
class OutlookPersonContext:
    contact_key: str
    directory_person_key: str
    display_name: str
    organization: str
    job_title: str
    org_unit: str
    role: str
    manager_key: str | None
    synthetic: bool = True
    live_observed: bool = False
    execution_performed: bool = False

    def __post_init__(self) -> None:
        if not self.synthetic:
            raise ValueError("Outlook person context must remain synthetic")
        if self.live_observed:
            raise ValueError("Outlook person context must not claim live observation")
        if self.execution_performed:
            raise ValueError("Outlook person context must not execute operations")
        for field_name in ("contact_key", "directory_person_key"):
            value = getattr(self, field_name)
            if not value or "@" in value or "://" in value:
                raise ValueError(f"{field_name} must remain opaque")

    def to_projection(self) -> dict[str, object]:
        return {
            "contact_key": self.contact_key,
            "directory_person_key": self.directory_person_key,
            "display_name": self.display_name,
            "organization": self.organization,
            "job_title": self.job_title,
            "org_unit": self.org_unit,
            "role": self.role,
            "manager_key": self.manager_key,
            "synthetic": True,
            "live_observed": False,
            "execution_performed": False,
        }


def build_synthetic_person_context(
    contact: SyntheticContact,
    directory_person: SyntheticDirectoryPerson,
) -> OutlookPersonContext:
    """Link two synthetic records only when their display identity agrees."""
    if contact.display_name != directory_person.display_name:
        raise ValueError("synthetic contact and directory person must describe the same person")
    return OutlookPersonContext(
        contact_key=contact.contact_key,
        directory_person_key=directory_person.person_key,
        display_name=contact.display_name,
        organization=contact.organization,
        job_title=contact.job_title,
        org_unit=directory_person.org_unit,
        role=directory_person.role,
        manager_key=directory_person.manager_key,
    )


__all__ = ["OutlookPersonContext", "build_synthetic_person_context"]
