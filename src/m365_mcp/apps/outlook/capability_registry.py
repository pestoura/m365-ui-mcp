"""Outlook-owned discovery capability declarations for live-read preparation.

These definitions establish semantic identities only. They do not enable the
Outlook application, register public tools, attest UI locators, or claim live
Microsoft 365 support. Effective support remains evidence-gated by the control
plane and Outlook stays RESERVED until the ordered promotion gates are met.
"""

from __future__ import annotations

from m365_mcp.application_registry import ApplicationKey
from m365_mcp.capability_registry import ScopedCapability


def _outlook_discovery_capability(capability: str) -> ScopedCapability:
    return ScopedCapability(
        application=ApplicationKey.OUTLOOK.value,
        surface="outlook_web",
        account_scope="professional_session",
        container_scope="account",
        capability=capability,
    )


def outlook_capability_definitions() -> tuple[ScopedCapability, ...]:
    """Return evidence-neutral Outlook read/discovery capability identities."""
    return (
        _outlook_discovery_capability("mail.read"),
        _outlook_discovery_capability("calendar.read"),
        _outlook_discovery_capability("people.read"),
        _outlook_discovery_capability("todo.read"),
        _outlook_discovery_capability("settings.read"),
    )


__all__ = ["outlook_capability_definitions"]
