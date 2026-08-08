from __future__ import annotations

from m365_mcp.apps.planner import planner_semantic_schemas, planner_tool_definitions
from m365_mcp.tool_registry import CompatibilityRequirement, MutationClass, default_tool_registry


def test_app_owned_planner_definitions_are_the_canonical_registry_source() -> None:
    definitions = planner_tool_definitions()
    registry = default_tool_registry()

    assert len(definitions) == 17
    assert registry.names() == tuple(definition.name for definition in definitions)
    assert registry.snapshot() == tuple(
        {
            "name": definition.name,
            "version": definition.version,
            "application": definition.application,
            "surface": definition.surface,
            "domain": definition.domain,
            "mutation_class": definition.mutation_class.value,
            "risk_class": definition.risk_class,
            "implementation_state": definition.implementation_state.value,
            "capability_keys": definition.capability_keys,
            "ui_contract_dependencies": definition.ui_contract_dependencies,
            "read_back_strategy": definition.read_back_strategy,
            "idempotency_semantics": definition.idempotency_semantics,
            "approval_requirement": definition.approval_requirement,
            "compatibility_requirement": definition.compatibility_requirement.value,
        }
        for definition in definitions
    )


def test_all_migrated_planner_definitions_preserve_public_contract() -> None:
    schemas = planner_semantic_schemas()
    definitions = planner_tool_definitions()

    assert tuple(definition.name for definition in definitions) == tuple(schemas)
    for definition in definitions:
        assert definition.application == "planner"
        assert definition.name.startswith("planner_")
        assert definition.mutation_class is MutationClass.READ
        assert definition.compatibility_requirement is CompatibilityRequirement.PRESERVE
        assert definition.input_schema == schemas[definition.name].input_schema
        assert definition.output_schema == schemas[definition.name].output_schema


def test_outlook_remains_absent_from_canonical_tool_registry() -> None:
    registry = default_tool_registry()

    assert registry.by_application("outlook") == ()
    assert not any(name.startswith("outlook_") for name in registry.names())
