"""Evidence-neutral Outlook capability discovery model for OUT-004."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from m365_mcp.apps.outlook.shell_contracts import OutlookShellTarget


class DiscoveryState(StrEnum):
    """Closed discovery states that do not imply live support."""

    UNOBSERVED = "UNOBSERVED"
    OBSERVED = "OBSERVED"
    BLOCKED = "BLOCKED"
    REATTESTATION_REQUIRED = "REATTESTATION_REQUIRED"


@dataclass(frozen=True)
class OutlookCapabilityCandidate:
    """One semantic capability candidate awaiting evidence-backed promotion."""

    capability_key: str
    shell_target: OutlookShellTarget
    shell_contract_key: str
    state: DiscoveryState = DiscoveryState.UNOBSERVED
    evidence_digest: str | None = None

    def __post_init__(self) -> None:
        if "." not in self.capability_key:
            raise ValueError("Outlook discovery capability must use namespace.action form")
        expected_contract = f"outlook.shell.{self.shell_target.value}"
        if self.shell_contract_key != expected_contract:
            raise ValueError("Outlook discovery candidate shell contract mismatch")
        if self.state is DiscoveryState.OBSERVED and self.evidence_digest is None:
            raise ValueError("observed Outlook capability requires evidence digest")
        if self.state is not DiscoveryState.OBSERVED and self.evidence_digest is not None:
            raise ValueError("unobserved Outlook capability cannot carry evidence digest")
        if self.evidence_digest is not None:
            if len(self.evidence_digest) != 64 or any(
                char not in "0123456789abcdef" for char in self.evidence_digest
            ):
                raise ValueError("Outlook discovery evidence digest must be SHA-256 hex")


def default_outlook_discovery_candidates() -> tuple[OutlookCapabilityCandidate, ...]:
    """Return initial read/discovery candidates without asserting support."""
    return (
        OutlookCapabilityCandidate(
            "mail.read",
            OutlookShellTarget.MAIL,
            "outlook.shell.mail",
        ),
        OutlookCapabilityCandidate(
            "calendar.read",
            OutlookShellTarget.CALENDAR,
            "outlook.shell.calendar",
        ),
        OutlookCapabilityCandidate(
            "people.read",
            OutlookShellTarget.PEOPLE,
            "outlook.shell.people",
        ),
        OutlookCapabilityCandidate(
            "todo.read",
            OutlookShellTarget.TODO,
            "outlook.shell.todo",
        ),
        OutlookCapabilityCandidate(
            "settings.read",
            OutlookShellTarget.SETTINGS,
            "outlook.shell.settings",
        ),
    )


__all__ = [
    "DiscoveryState",
    "OutlookCapabilityCandidate",
    "default_outlook_discovery_candidates",
]
