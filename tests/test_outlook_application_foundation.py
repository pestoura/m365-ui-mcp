from __future__ import annotations

from m365_mcp.application_registry import (
    ApplicationKey,
    ApplicationState,
    default_application_registry,
)
from m365_mcp.apps.outlook import foundation_manifest
from m365_mcp.tool_registry import default_tool_registry


def test_outlook_foundation_matches_closed_application_registry() -> None:
    registration = default_application_registry().get(ApplicationKey.OUTLOOK)
    manifest = foundation_manifest()

    assert registration.state is ApplicationState.RESERVED
    assert registration.registrar is None
    assert registration.capability_namespace == "outlook"
    assert manifest.application is ApplicationKey.OUTLOOK
    assert manifest.state is ApplicationState.RESERVED
    assert manifest.capability_namespace == registration.capability_namespace


def test_outlook_foundation_exposes_no_public_execution_surface() -> None:
    manifest = foundation_manifest()
    registry = default_tool_registry()

    assert manifest.public_tools_enabled is False
    assert manifest.browser_operations_enabled is False
    assert registry.by_application("outlook") == ()
    assert not any(name.startswith("outlook_") for name in registry.names())
