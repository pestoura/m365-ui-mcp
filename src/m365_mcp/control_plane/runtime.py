"""Application-neutral FastMCP control-plane construction.

This module deliberately has no Planner/Outlook imports. Application modules
own semantic tool registration and are injected by the composition root.
"""

from __future__ import annotations

from typing import Any, Protocol

from m365_mcp.config import Settings


class ToolRegistrar(Protocol):
    """Closed registration hook supplied by an enabled application adapter."""

    def __call__(self, server: Any, settings: Settings, /) -> None:
        """Register semantic MCP tools on ``server``."""
        ...


def build_control_plane(
    settings: Settings,
    *,
    name: str,
    version: str,
    register_tools: ToolRegistrar,
) -> Any:
    """Build an MCP server and project semantic tools through one registrar.

    The generic runtime knows nothing about Planner, Outlook, browser selectors
    or arbitrary execution. Multi-application registry/projection arrives in
    CORE-007..010; this single registrar keeps CORE-005 behavior-preserving.
    """
    from fastmcp import FastMCP  # lazy import keeps dependency boundary explicit

    server = FastMCP(name=name, version=version)
    register_tools(server, settings)
    return server
