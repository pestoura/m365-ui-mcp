"""Outlook application foundation.

OUT-001 creates an application-owned package boundary, OUT-002 adds synthetic
isolated fixtures, and OUT-003 adds semantic shell/navigation requirements.
Outlook remains RESERVED and exposes no public MCP registrar or browser
operation surface.
"""

from m365_mcp.apps.outlook.manifest import OutlookFoundationManifest, foundation_manifest
from m365_mcp.apps.outlook.mock_ui import (
    MockMessage,
    OutlookMockFixture,
    default_outlook_fixture,
)
from m365_mcp.apps.outlook.shell_contracts import (
    OutlookShellContract,
    OutlookShellTarget,
    outlook_shell_contracts,
)

__all__ = [
    "MockMessage",
    "OutlookFoundationManifest",
    "OutlookMockFixture",
    "OutlookShellContract",
    "OutlookShellTarget",
    "default_outlook_fixture",
    "foundation_manifest",
    "outlook_shell_contracts",
]
