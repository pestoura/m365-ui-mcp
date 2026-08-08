"""CORE-011 scoped Capability Registry acceptance tests."""

from __future__ import annotations

import m365_mcp.capability_registry
import m365_mcp.tool_registry
import planner_mcp.capabilities
import pytest


EXPECTED_PLANNER_CAPABILITIES = (
    "plans.read",
    "tasks.read",
    "buckets.read",
    "dependencies.read",
    "scheduling.read",
    "goals.read",
    "sprints.read",
    "resources.read",
    "custom_fields.read",
    "portfolios.read",
    "project_snapshot.read",
)


def test_default_registry_preserves_planner_capability_order_and_scope() -> None:
    registry = m365_mcp.capability_registry.default_capability_registry()
    definitions = registry.by_application("planner")

    assert registry.capability_names("planner") == EXPECTED_PLANNER_CAPABILITIES
    assert registry.by_application("outlook") == ()
    assert len(definitions) == 11
    assert all(item.application == "planner" for item in definitions)
    assert all(item.surface == "planner_web" for item in definitions)
    assert all(item.account_scope == "professional_session" for item in definitions)
    assert {item.container_scope for item in definitions} == {"account", "plan"}


def test_scoped_identity_uses_all_required_dimensions() -> None:
    registry = m365_mcp.capability_registry.default_capability_registry()
    definition = registry.get_scoped(
        application="planner",
        surface="planner_web",
        account_scope="professional_session",
        container_scope="plan",
        capability="tasks.read",
    )
    assert definition.identity == (
        "planner",
        "planner_web",
        "professional_session",
        "plan",
        "tasks.read",
    )


def test_same_semantic_capability_can_exist_in_distinct_container_scopes() -> None:
    first = m365_mcp.capability_registry.ScopedCapability(
        "planner", "planner_web", "professional_session", "plan", "tasks.read"
    )
    second = m365_mcp.capability_registry.ScopedCapability(
        "planner", "planner_web", "professional_session", "account", "tasks.read"
    )
    registry = m365_mcp.capability_registry.CapabilityRegistry((first, second))

    assert registry.capability_names("planner") == ("tasks.read",)
    assert len(registry.definitions()) == 2


def test_duplicate_exact_scope_fails_closed() -> None:
    definition = m365_mcp.capability_registry.ScopedCapability(
        "planner", "planner_web", "professional_session", "plan", "tasks.read"
    )
    with pytest.raises(ValueError, match="duplicate scoped capability"):
        m365_mcp.capability_registry.CapabilityRegistry((definition, definition))


def test_tool_registry_capability_keys_are_backed_by_capability_registry() -> None:
    capabilities = m365_mcp.capability_registry.default_capability_registry()
    for tool in m365_mcp.tool_registry.default_tool_registry().by_application("planner"):
        for key in tool.capability_keys:
            assert capabilities.has_capability("planner", key), (tool.name, key)


def test_existing_planner_capability_output_names_are_preserved() -> None:
    result = planner_mcp.capabilities.build_capabilities(runtime_ok=True)
    assert tuple(item["capability"] for item in result["capabilities"]) == (
        EXPECTED_PLANNER_CAPABILITIES
    )


def test_registry_snapshot_contains_scope_classes_not_tenant_ids() -> None:
    rendered = str(m365_mcp.capability_registry.default_capability_registry().snapshot()).lower()
    assert "@" not in rendered
    assert "mailbox" not in rendered
    assert "tenant_id" not in rendered
    assert "account_id" not in rendered
