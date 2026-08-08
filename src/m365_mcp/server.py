"""Canonical M365 MCP composition root.

The generic control plane is application-neutral. CORE-007 introduces a closed
Application Registry while preserving the exact Planner-only public projection
until Planner parity allows the ordered Outlook phase to start.
"""

from __future__ import annotations

import json
import sys
from typing import Any

from m365_mcp.application_registry import default_application_registry
from m365_mcp.config import Settings, load_settings
from m365_mcp.control_plane import build_control_plane
from m365_mcp.version import __version__
from planner_mcp.errors import ConfigurationError
from planner_mcp.logging_setup import configure_logging
from planner_mcp.state import initialise


def build_server(settings: Settings | None = None) -> Any:
    """Build the current Planner-compatible projection on generic M365 core."""
    resolved = settings or load_settings()
    applications = default_application_registry()
    return build_control_plane(
        resolved,
        name="planner-mcp",
        version=__version__,
        register_tools=applications.register_enabled_tools,
    )


def run() -> None:
    """Run Streamable HTTP, failing closed on invalid configuration."""
    try:
        settings = load_settings()
    except ConfigurationError as exc:
        print(json.dumps(exc.to_dict(), sort_keys=True), file=sys.stderr)
        raise SystemExit(2) from None

    configure_logging(settings.log_level)
    initialise(settings.state_path)
    server = build_server(settings)
    server.run(transport="http", host=settings.host, port=settings.port)
