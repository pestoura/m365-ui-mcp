"""CORE-011 scoped Capability Registry acceptance tests."""

from __future__ import annotations

import importlib
from typing import Any

import pytest

application_registry: Any = importlib.import_module("m365_mcp.application_registry")
capability_registry: Any = importlib.import_module("m365_mcp.capability_registry")
tool_registry: Any = importlib.import_module("m365_mcp.tool_registry")
planner_capabilities: Any = importlib.import_module("planner_mcp.capabilities")


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

EXPECTED_OUTLOOK_DISCOVERY_CAPABILITIES = (
    "mail.read",
    "calendar.read",
    "people.read",
    "todo.read",
    "settings.read",
)


def test_default_registry_preserves_planner_capability_order_and_scope() -> None:
    registry = capability_registry.default_capability_registry()
    definitions = registry.by_application("planner")

    assert registry.capability_names("planner") == EXPECTED_PLANNER_CAPABILITIES
    assert len(definitions) == 11
    assert all(item.application == "planner" for item in definitions)
    assert all(item.surface == "planner_web" for item in definitions)
    assert all(item.account_scope == "professional_session" for item in definitions)
    assert {item.container_scope for item in definitions} == {"account", "plan"}


def test_outlook_discovery_capabilities_are_declared_without_execution_promotion() -> None:
    capabilities = capability_registry.default_capability_registry()
    definitions = capabilities.by_application("outlook")
    applications = application_registry.default_application_registry()

    assert capabilities.capability_names("outlook") == EXPECTED_OUTLOOK_DISCOVERY_CAPABILITIES
    assert len(definitions) == 5
    assert all(item.application == "outlook" for item in definitions)
    assert all(item.surface == "outlook_web" for item in definitions)
    assert all(item.account_scope == "professional_session" for item in definitions)
    assert all(item.container_scope == "account" for item in definitions)
    outlook = applications.get(application_registry.ApplicationKey.OUTLOOK)
    assert outlook.state is application_registry.ApplicationState.RESERVED
    assert tool_registry.default_tool_registry().by_application("outlook") == ()


def test_scoped_identity_uses_all_required_dimensions() -> None:
    registry = capability_registry.default_capability_registry()
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
    first = capability_registry.ScopedCapability(
        "planner", "planner_web", "professional_session", "plan", "tasks.read"
    )
    second = capability_registry.ScopedCapability(
        "planner", "planner_web", "professional_session", "account", "tasks.read"
    )
    registry = capability_registry.CapabilityRegistry((first, second))

    assert registry.capability_names("planner") == ("tasks.read",)
    assert len(registry.definitions()) == 2


def test_duplicate_exact_scope_fails_closed() -> None:
    definition = capability_registry.ScopedCapability(
        "planner", "planner_web", "professional_session", "plan", "tasks.read"
    )
    with pytest.raises(ValueError, match="duplicate scoped capability"):
        capability_registry.CapabilityRegistry((definition, definition))


def test_tool_registry_capability_keys_are_backed_by_capability_registry() -> None:
    capabilities = capability_registry.default_capability_registry()
    for tool in tool_registry.default_tool_registry().by_application("planner"):
        for key in tool.capability_keys:
            assert capabilities.has_capability("planner", key), (tool.name, key)


def test_existing_planner_capability_output_names_are_preserved() -> None:
    result = planner_capabilities.build_capabilities(runtime_ok=True)
    assert tuple(item["capability"] for item in result["capabilities"]) == (
        EXPECTED_PLANNER_CAPABILITIES
    )


def test_registry_snapshot_contains_scope_classes_not_tenant_ids() -> None:
    rendered = str(capability_registry.default_capability_registry().snapshot()).lower()
    assert "@" not in rendered
    assert "mailbox" not in rendered
    assert "tenant_id" not in rendered
    assert "account_id" not in rendered
