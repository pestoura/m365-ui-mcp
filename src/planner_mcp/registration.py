"""Planner semantic tool registration for the generic M365 control plane."""

from __future__ import annotations

from typing import Any

from m365_mcp.config import Settings

from .tools import PlannerTools


def register_planner_tools(mcp: Any, settings: Settings) -> None:
    """Register the immutable 0.1.0 Planner public tool surface.

    Explicit wrappers intentionally preserve FastMCP signatures/schemas while
    the generic control plane is extracted. Dynamic metadata-driven projection
    is introduced later under CORE-008/009, not simulated here.
    """
    tools = PlannerTools(settings)

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
