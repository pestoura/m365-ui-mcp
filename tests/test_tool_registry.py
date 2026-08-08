"""CORE-008 canonical Tool Registry acceptance tests."""

from __future__ import annotations

import pytest

from m365_mcp.tool_registry import (
    CompatibilityRequirement,
    ImplementationState,
    ToolRegistry,
    default_tool_registry,
)
from planner_mcp.contracts import load_contract
from planner_mcp.tools import TOOL_NAMES


def test_registry_matches_all_current_public_contract_surfaces() -> None:
    registry = default_tool_registry()
    manifest_names = {tool["name"] for tool in load_contract("tool_manifest")["tools"]}
    extended_names = {
        tool["name"] for tool in load_contract("extended_tool_manifest")["tools"]
    }

    assert len(registry.names()) == 17
    assert set(registry.names()) == set(TOOL_NAMES) == manifest_names == extended_names
    assert all(name.startswith("planner_") for name in registry.names())
    assert registry.by_application("outlook") == ()


def test_current_registry_preserves_planner_and_does_not_overclaim_live_support() -> None:
    registry = default_tool_registry()

    for definition in registry.by_application("planner"):
        assert definition.compatibility_requirement is CompatibilityRequirement.PRESERVE
        assert definition.mutation_class.value == "READ"
        assert definition.approval_requirement == "none"
        assert definition.input_schema["type"] == "object"
        assert definition.output_schema["type"] == "object"
        assert definition.implementation_state in {
            ImplementationState.IMPLEMENTED_MOCK_ONLY,
            ImplementationState.IMPLEMENTED_NOT_ATTESTED,
        }


def test_parameterized_tool_schemas_match_public_signatures() -> None:
    registry = default_tool_registry()

    assert registry.get("planner_plan_get").input_schema["required"] == ["plan_id"]
    assert registry.get("planner_task_list").input_schema["required"] == ["plan_id"]
    assert registry.get("planner_task_get").input_schema["required"] == ["task_id"]
    assert registry.get("planner_project_snapshot").input_schema["required"] == ["plan_id"]
    assert registry.get("planner_health").input_schema["required"] == []


def test_auth_start_retains_current_special_idempotency_and_readback() -> None:
    definition = default_tool_registry().get("planner_auth_start")
    assert definition.idempotency_semantics == "key_required"
    assert definition.read_back_strategy == "AUTH_STATE_RE_READ"
    assert definition.risk_class == "SESSION_INTERACTION"


def test_duplicate_tool_definitions_fail_closed() -> None:
    first = default_tool_registry().get("planner_health")
    with pytest.raises(ValueError, match="duplicate tool definition"):
        ToolRegistry((first, first))
