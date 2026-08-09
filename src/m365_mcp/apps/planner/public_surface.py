"""Canonical preserved Planner public MCP tool names.

PLN-MIG-006 makes the compatibility surface explicit inside the Planner
application boundary. The tuple is an ABI contract: names and order must remain
stable throughout the M365 migration unless a later explicitly versioned
breaking change is approved.
"""

from __future__ import annotations

PLANNER_PUBLIC_TOOL_NAMES: tuple[str, ...] = (
    "planner_health",
    "planner_readiness",
    "planner_capabilities",
    "planner_agent_card",
    "planner_ui_contract_status",
    "planner_auth_status",
    "planner_auth_start",
    "planner_auth_resume",
    "planner_auth_session_info",
    "planner_plan_list",
    "planner_plan_get",
    "planner_task_list",
    "planner_task_get",
    "planner_project_snapshot",
    "planner_account_context",
    "planner_license_capabilities",
    "planner_smoke_test",
)


def planner_public_tool_names() -> tuple[str, ...]:
    """Return the immutable canonical Planner public-tool sequence."""
    return PLANNER_PUBLIC_TOOL_NAMES


__all__ = ["PLANNER_PUBLIC_TOOL_NAMES", "planner_public_tool_names"]
