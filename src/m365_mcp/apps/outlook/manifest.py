"""Non-executable Outlook application foundation metadata for OUT-001."""

from __future__ import annotations

from dataclasses import dataclass

from m365_mcp.application_registry import ApplicationKey, ApplicationState


@dataclass(frozen=True)
class OutlookFoundationManifest:
    """Bounded metadata describing the reserved Outlook application boundary."""

    application: ApplicationKey = ApplicationKey.OUTLOOK
    state: ApplicationState = ApplicationState.RESERVED
    capability_namespace: str = "outlook"
    public_tools_enabled: bool = False
    browser_operations_enabled: bool = False


def foundation_manifest() -> OutlookFoundationManifest:
    """Return the inert OUT-001 foundation manifest."""
    return OutlookFoundationManifest()


__all__ = ["OutlookFoundationManifest", "foundation_manifest"]
