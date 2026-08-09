"""Semantic Outlook shell/navigation contracts for OUT-003.

These contracts describe *what* later discovery must identify, not how to
locate it. No CSS/XPath/URL/browser command is embedded here and every live
state remains explicitly unverified until evidence-backed attestation exists.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class OutlookShellTarget(StrEnum):
    """Closed first-party Outlook surfaces required by the product roadmap."""

    MAIL = "mail"
    CALENDAR = "calendar"
    PEOPLE = "people"
    TODO = "todo"
    SETTINGS = "settings"


@dataclass(frozen=True)
class OutlookShellContract:
    """Tenant-neutral semantic requirement for one Outlook shell target."""

    contract_key: str
    target: OutlookShellTarget
    semantic_role: str
    requires_authenticated_shell: bool = True
    live_evidence_state: str = "UNVERIFIED_LIVE"

    def __post_init__(self) -> None:
        if not self.contract_key.startswith("outlook.shell."):
            raise ValueError("Outlook shell contract key must use outlook.shell namespace")
        if not self.semantic_role or self.semantic_role != self.semantic_role.strip():
            raise ValueError("Outlook shell semantic role is required")
        if self.live_evidence_state != "UNVERIFIED_LIVE":
            raise ValueError("OUT-003 cannot claim live shell attestation")


def outlook_shell_contracts() -> tuple[OutlookShellContract, ...]:
    """Return the deterministic OUT-003 navigation contract set."""
    return (
        OutlookShellContract(
            contract_key="outlook.shell.mail",
            target=OutlookShellTarget.MAIL,
            semantic_role="mail_navigation",
        ),
        OutlookShellContract(
            contract_key="outlook.shell.calendar",
            target=OutlookShellTarget.CALENDAR,
            semantic_role="calendar_navigation",
        ),
        OutlookShellContract(
            contract_key="outlook.shell.people",
            target=OutlookShellTarget.PEOPLE,
            semantic_role="people_navigation",
        ),
        OutlookShellContract(
            contract_key="outlook.shell.todo",
            target=OutlookShellTarget.TODO,
            semantic_role="todo_navigation",
        ),
        OutlookShellContract(
            contract_key="outlook.shell.settings",
            target=OutlookShellTarget.SETTINGS,
            semantic_role="settings_navigation",
        ),
    )


__all__ = ["OutlookShellContract", "OutlookShellTarget", "outlook_shell_contracts"]
