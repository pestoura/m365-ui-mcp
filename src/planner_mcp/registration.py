"""Planner semantic tool registration for the generic M365 control plane.

Registry metadata controls exposure order and CORE-010 profiles may narrow that
exposure. Handlers remain explicit, closed and typed; profiles never alter tool
governance metadata or introduce a generic executor.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from m365_mcp.config import Settings
from m365_mcp.tool_profiles import project_tool_definitions
from m365_mcp.tool_registry import default_tool_registry

from .tools import PlannerTools

ToolHandler = Callable[..., Awaitable[dict[str, Any]]]


def _planner_bindings(tools: PlannerTools) -> dict[str, ToolHandler]:
    """Build the closed set of typed Planner handlers for registry projection."""

    async def planner_health() -> dict[str, Any]:
        """Liveness of the control plane."""
        return await tools.planner_health()

    async def planner_readiness() -> dict[str, Any]:
        """Readiness across SQLite, browser worker and UIContract."""
        return await tools.planner_readiness()

    async def planner_capabilities() -> dict[str, Any]:
        """Evidence-based Planner Premium capability model."""
        return await tools.planner_capabilities()

    async def planner_agent_card() -> dict[str, Any]:
        """Agent card and tool manifests."""
        return await tools.planner_agent_card()

    async def planner_ui_contract_status() -> dict[str, Any]:
        """Versioned UIContract attestation status."""
        return await tools.planner_ui_contract_status()

    async def planner_auth_status() -> dict[str, Any]:
        """Current auth state."""
        return await tools.planner_auth_status()

    async def planner_auth_start() -> dict[str, Any]:
        """Start an interactive auth attempt."""
        return await tools.planner_auth_start()

    async def planner_auth_resume() -> dict[str, Any]:
        """Resume a pending auth attempt."""
        return await tools.planner_auth_resume()

    async def planner_auth_session_info() -> dict[str, Any]:
        """Sanitized persistent-profile session info."""
        return await tools.planner_auth_session_info()

    async def planner_plan_list() -> dict[str, Any]:
        """List plans."""
        return await tools.planner_plan_list()

    async def planner_plan_get(plan_id: str) -> dict[str, Any]:
        """Read a plan."""
        return await tools.planner_plan_get(plan_id)

    async def planner_task_list(plan_id: str) -> dict[str, Any]:
        """List tasks of a plan."""
        return await tools.planner_task_list(plan_id)

    async def planner_task_get(task_id: str) -> dict[str, Any]:
        """Read a task."""
        return await tools.planner_task_get(task_id)

    async def planner_project_snapshot(plan_id: str) -> dict[str, Any]:
        """Composite read-only snapshot."""
        return await tools.planner_project_snapshot(plan_id)

    async def planner_account_context() -> dict[str, Any]:
        """Sanitized account/tenant context."""
        return await tools.planner_account_context()

    async def planner_license_capabilities() -> dict[str, Any]:
        """License-derived capability evidence."""
        return await tools.planner_license_capabilities()

    async def planner_smoke_test() -> dict[str, Any]:
        """Read-only smoke test."""
        return await tools.planner_smoke_test()

    return {
        planner_health.__name__: planner_health,
        planner_readiness.__name__: planner_readiness,
        planner_capabilities.__name__: planner_capabilities,
        planner_agent_card.__name__: planner_agent_card,
        planner_ui_contract_status.__name__: planner_ui_contract_status,
        planner_auth_status.__name__: planner_auth_status,
        planner_auth_start.__name__: planner_auth_start,
        planner_auth_resume.__name__: planner_auth_resume,
        planner_auth_session_info.__name__: planner_auth_session_info,
        planner_plan_list.__name__: planner_plan_list,
        planner_plan_get.__name__: planner_plan_get,
        planner_task_list.__name__: planner_task_list,
        planner_task_get.__name__: planner_task_get,
        planner_project_snapshot.__name__: planner_project_snapshot,
        planner_account_context.__name__: planner_account_context,
        planner_license_capabilities.__name__: planner_license_capabilities,
        planner_smoke_test.__name__: planner_smoke_test,
    }


def register_planner_tools(mcp: Any, settings: Settings) -> None:
    """Register the bounded Planner projection from validated registry metadata."""
    tools = PlannerTools(settings)
    registry = default_tool_registry()
    all_planner_definitions = registry.by_application("planner")
    bindings = _planner_bindings(tools)
    expected_names = tuple(definition.name for definition in all_planner_definitions)

    if set(bindings) != set(expected_names):
        missing = sorted(set(expected_names) - set(bindings))
        unexpected = sorted(set(bindings) - set(expected_names))
        raise RuntimeError(
            "Planner registry/binding mismatch: "
            f"missing={missing!r} unexpected={unexpected!r}"
        )

    exposed_names = {
        definition.name
        for definition in project_tool_definitions(registry, settings.tool_profile)
    }
    definitions = tuple(
        definition
        for definition in all_planner_definitions
        if definition.name in exposed_names
    )

    for definition in definitions:
        mcp.tool()(bindings[definition.name])
