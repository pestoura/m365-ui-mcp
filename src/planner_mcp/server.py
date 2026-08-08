"""FastMCP Streamable HTTP control plane."""

from __future__ import annotations

import json
import sys
from typing import Any

from .config import Settings, load_settings
from .errors import ConfigurationError
from .logging_setup import configure_logging
from .state import initialise
from .tools import PlannerTools


def build_server(settings: Settings | None = None) -> Any:
    """Create the FastMCP server with the 17 read-only tools registered."""
    from fastmcp import FastMCP  # imported lazily to keep unit tests dependency-light

    settings = settings or load_settings()
    tools = PlannerTools(settings)
    mcp = FastMCP(name="planner-mcp", version="0.1.0")

    @mcp.tool()
    async def planner_health() -> dict[str, Any]:
        """Liveness of the control plane."""
        return await tools.planner_health()

    @mcp.tool()
    async def planner_readiness() -> dict[str, Any]:
        """Readiness across SQLite, browser worker and UIContract."""
        return await tools.planner_readiness()

    @mcp.tool()
    async def planner_capabilities() -> dict[str, Any]:
        """Evidence-based Planner Premium capability model."""
        return await tools.planner_capabilities()

    @mcp.tool()
    async def planner_agent_card() -> dict[str, Any]:
        """Agent card and tool manifests."""
        return await tools.planner_agent_card()

    @mcp.tool()
    async def planner_ui_contract_status() -> dict[str, Any]:
        """Versioned UIContract attestation status."""
        return await tools.planner_ui_contract_status()

    @mcp.tool()
    async def planner_auth_status() -> dict[str, Any]:
        """Current auth state."""
        return await tools.planner_auth_status()

    @mcp.tool()
    async def planner_auth_start() -> dict[str, Any]:
        """Start an interactive auth attempt."""
        return await tools.planner_auth_start()

    @mcp.tool()
    async def planner_auth_resume() -> dict[str, Any]:
        """Resume a pending auth attempt."""
        return await tools.planner_auth_resume()

    @mcp.tool()
    async def planner_auth_session_info() -> dict[str, Any]:
        """Sanitized persistent-profile session info."""
        return await tools.planner_auth_session_info()

    @mcp.tool()
    async def planner_plan_list() -> dict[str, Any]:
        """List plans."""
        return await tools.planner_plan_list()

    @mcp.tool()
    async def planner_plan_get(plan_id: str) -> dict[str, Any]:
        """Read a plan."""
        return await tools.planner_plan_get(plan_id)

    @mcp.tool()
    async def planner_task_list(plan_id: str) -> dict[str, Any]:
        """List tasks of a plan."""
        return await tools.planner_task_list(plan_id)

    @mcp.tool()
    async def planner_task_get(task_id: str) -> dict[str, Any]:
        """Read a task."""
        return await tools.planner_task_get(task_id)

    @mcp.tool()
    async def planner_project_snapshot(plan_id: str) -> dict[str, Any]:
        """Composite read-only snapshot."""
        return await tools.planner_project_snapshot(plan_id)

    @mcp.tool()
    async def planner_account_context() -> dict[str, Any]:
        """Sanitized account/tenant context."""
        return await tools.planner_account_context()

    @mcp.tool()
    async def planner_license_capabilities() -> dict[str, Any]:
        """License-derived capability evidence."""
        return await tools.planner_license_capabilities()

    @mcp.tool()
    async def planner_smoke_test() -> dict[str, Any]:
        """Read-only smoke test."""
        return await tools.planner_smoke_test()

    return mcp


def run() -> None:
    """Run the Streamable HTTP MCP server, failing closed on invalid configuration."""
    try:
        settings = load_settings()
    except ConfigurationError as exc:
        print(json.dumps(exc.to_dict(), sort_keys=True), file=sys.stderr)
        raise SystemExit(2) from None

    configure_logging(settings.log_level)
    initialise(settings.state_path)
    server = build_server(settings)
    server.run(transport="http", host=settings.host, port=settings.port)
