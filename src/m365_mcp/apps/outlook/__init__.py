"""Outlook application foundation.

OUT-001 creates an application-owned package boundary and OUT-002 adds only
synthetic isolated fixtures. Outlook remains RESERVED in the Application
Registry and this package exposes no public MCP registrar or browser operation
surface.
"""

from m365_mcp.apps.outlook.manifest import OutlookFoundationManifest, foundation_manifest
from m365_mcp.apps.outlook.mock_ui import (
    MockMessage,
    OutlookMockFixture,
    default_outlook_fixture,
)

__all__ = [
    "MockMessage",
    "OutlookFoundationManifest",
    "OutlookMockFixture",
    "default_outlook_fixture",
    "foundation_manifest",
]
