"""Canonical M365 MCP composition root.

The generic control plane is application-neutral. CORE-007 introduces a closed
Application Registry while preserving the exact Planner-only public projection
until Planner parity allows the ordered Outlook phase to start.
"""

from __future__ import annotations

import json
import sys
from typing import Any

import uvicorn

from m365_mcp.application_registry import default_application_registry
from m365_mcp.config import Settings, load_settings
from m365_mcp.control_plane import build_control_plane
from m365_mcp.origin_auth import OriginBearerMiddleware, load_origin_bearer_token
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
        origin_bearer = load_origin_bearer_token()
    except ConfigurationError as exc:
        print(json.dumps(exc.to_dict(), sort_keys=True), file=sys.stderr)
        raise SystemExit(2) from None

    configure_logging(settings.log_level)
    initialise(settings.state_path)
    server = build_server(settings)

    if origin_bearer is None:
        server.run(transport="http", host=settings.host, port=settings.port)
        return

    # FastMCP's ASGI surface preserves Streamable HTTP semantics while allowing
    # the portal-to-origin bearer boundary to execute before MCP handlers.
    app = OriginBearerMiddleware(server.http_app(), origin_bearer)
    uvicorn.run(
        app,
        host=settings.host,
        port=settings.port,
        log_level=settings.log_level.lower(),
    )
