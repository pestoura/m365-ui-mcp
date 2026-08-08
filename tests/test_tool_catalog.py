"""Tests for the 0.1.0 tool catalogue and its invariants."""

from __future__ import annotations

import pytest

from planner_mcp.contracts import ExtendedToolManifest
from planner_mcp.enums import ApprovalRequirement, MutationClass, TrustLevel
from planner_mcp.tool_catalog import (
    CATALOG_0_1_0,
    CATALOG_BY_NAME,
    FORBIDDEN_NAME_FRAGMENTS,
)

REQUIRED = {
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
}


def test_required_tools_present() -> None:
    assert set(CATALOG_BY_NAME) >= REQUIRED


def test_catalog_has_no_duplicates() -> None:
    assert len(CATALOG_BY_NAME) == len(CATALOG_0_1_0)


@pytest.mark.parametrize("tool", CATALOG_0_1_0, ids=lambda t: t.name)
def test_every_tool_is_read_only_in_0_1_0(tool: ExtendedToolManifest) -> None:
    assert tool.mutation_class is MutationClass.READ
    assert tool.approval_requirement is ApprovalRequirement.NONE
    assert tool.reversible is True
    assert tool.drift_behavior == "FAIL_CLOSED"


@pytest.mark.parametrize("tool", CATALOG_0_1_0, ids=lambda t: t.name)
def test_no_generic_browser_primitives(tool: ExtendedToolManifest) -> None:
    suffix = tool.name.removeprefix("planner_")
    assert not any(fragment in suffix for fragment in FORBIDDEN_NAME_FRAGMENTS)


@pytest.mark.parametrize("tool", CATALOG_0_1_0, ids=lambda t: t.name)
def test_every_tool_binds_a_policy_rule(tool: ExtendedToolManifest) -> None:
    assert tool.policy_rule_id.startswith("POL-")


def test_interactive_auth_tools_are_privileged() -> None:
    for name in ("planner_auth_start", "planner_auth_resume"):
        assert CATALOG_BY_NAME[name].trust_level is TrustLevel.PRIVILEGED


def test_tool_names_are_namespaced() -> None:
    assert all(tool.name.startswith("planner_") for tool in CATALOG_0_1_0)


def test_catalog_serialises_to_schema_shape() -> None:
    payload = CATALOG_0_1_0[0].as_dict()
    assert payload["mutation_class"] == "READ"
    assert payload["drift_behavior"] == "FAIL_CLOSED"
    assert isinstance(payload["required_locks"], list)
