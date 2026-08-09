from __future__ import annotations

from m365_mcp import tool_registry
from m365_mcp.apps.planner import public_surface
from planner_mcp import tools as legacy_tools

EXPECTED_PUBLIC_NAMES = (
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


def test_canonical_public_tool_abi_preserves_exact_17_names_and_order() -> None:
    assert public_surface.PLANNER_PUBLIC_TOOL_NAMES == EXPECTED_PUBLIC_NAMES
    assert public_surface.planner_public_tool_names() == EXPECTED_PUBLIC_NAMES
    assert len(set(EXPECTED_PUBLIC_NAMES)) == 17


def test_registry_and_legacy_surface_match_canonical_public_abi() -> None:
    definitions = tool_registry.default_tool_registry().by_application("planner")

    assert tuple(definition.name for definition in definitions) == EXPECTED_PUBLIC_NAMES
    assert legacy_tools.TOOL_NAMES == EXPECTED_PUBLIC_NAMES
    assert all(
        definition.compatibility_requirement
        is tool_registry.CompatibilityRequirement.PRESERVE
        for definition in definitions
    )


def test_public_abi_does_not_activate_outlook_or_generic_names() -> None:
    assert all(name.startswith("planner_") for name in EXPECTED_PUBLIC_NAMES)
    assert not any(name.startswith("outlook_") for name in EXPECTED_PUBLIC_NAMES)
    assert not any("browser" in name or "execute" in name for name in EXPECTED_PUBLIC_NAMES)
