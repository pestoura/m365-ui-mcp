"""Outlook application foundation.

OUT-001 creates an application-owned package boundary only. Outlook remains
RESERVED in the Application Registry and this package exposes no public MCP
registrar or browser operation surface.
"""

from m365_mcp.apps.outlook.manifest import OutlookFoundationManifest, foundation_manifest

__all__ = ["OutlookFoundationManifest", "foundation_manifest"]
