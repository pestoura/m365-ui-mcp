from __future__ import annotations

from m365_mcp.apps.planner import planner_capability_definitions


EXPECTED_CAPABILITIES = (
    ("plans.read", "account"),
    ("tasks.read", "plan"),
    ("buckets.read", "plan"),
    ("dependencies.read", "plan"),
    ("scheduling.read", "plan"),
    ("goals.read", "plan"),
    ("sprints.read", "plan"),
    ("resources.read", "plan"),
    ("custom_fields.read", "plan"),
    ("portfolios.read", "account"),
    ("project_snapshot.read", "plan"),
)


def test_planner_app_owns_all_11_canonical_capability_definitions() -> None:
    definitions = planner_capability_definitions()

    assert len(definitions) == 11
    assert tuple(
        (definition.capability, definition.container_scope) for definition in definitions
    ) == EXPECTED_CAPABILITIES
    assert all(definition.application == "planner" for definition in definitions)
    assert all(definition.surface == "planner_web" for definition in definitions)
    assert all(
        definition.account_scope == "professional_session" for definition in definitions
    )


def test_default_capability_registry_is_composed_from_planner_app_definitions() -> None:
    import m365_mcp.capability_registry as capability_registry

    app_definitions = planner_capability_definitions()
    registry = capability_registry.default_capability_registry()

    assert registry.definitions() == app_definitions
    assert registry.by_application("planner") == app_definitions
    assert registry.by_application("outlook") == ()


def test_capability_migration_preserves_scope_aware_policy_for_all_planner_tools() -> None:
    import m365_mcp.config as config

    import m365_mcp.policy as policy

    import m365_mcp.tool_registry as tool_registry

    engine = policy.MetadataPolicyEngine()
    tools = tool_registry.default_tool_registry().by_application("planner")

    assert len(tools) == 17
    for definition in tools:
        result = engine.evaluate(definition.name, config.Settings())
        assert result.decision is policy.Decision.ALLOW
        assert result.scope is not None
        assert result.scope.application == "planner"
        assert result.scope.surface == definition.surface
