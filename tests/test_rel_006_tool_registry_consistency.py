"""REL-006 — Tool Registry schema and cross-surface consistency assurance.

These tests are assurance-only. They add no product behaviour and assert
invariants over the canonical registry that must hold for every application
added later, not only for the preserved Planner surface.
"""

from __future__ import annotations

from typing import Any

import pytest

from m365_mcp.application_registry import ApplicationKey
from m365_mcp.tool_registry import (
    CompatibilityRequirement,
    ImplementationState,
    MutationClass,
    ToolDefinition,
    default_tool_registry,
)
from planner_mcp.contracts import load_contract

_ALLOWED_APPLICATION_PREFIXES = {"core": "m365_"} | {
    key.value: f"{key.value}_" for key in ApplicationKey
}


def _definitions() -> tuple[ToolDefinition, ...]:
    registry = default_tool_registry()
    return tuple(registry.get(name) for name in registry.names())


def _schema_is_object(schema: dict[str, Any]) -> bool:
    return schema.get("type") == "object" and isinstance(schema.get("properties", {}), dict)


def test_every_definition_carries_complete_governance_metadata() -> None:
    for definition in _definitions():
        assert definition.version
        assert definition.surface.strip()
        assert definition.domain.strip()
        assert definition.risk_class.strip()
        assert definition.read_back_strategy.strip()
        assert definition.idempotency_semantics.strip()
        assert definition.approval_requirement.strip()
        assert isinstance(definition.mutation_class, MutationClass)
        assert isinstance(definition.implementation_state, ImplementationState)
        assert isinstance(definition.compatibility_requirement, CompatibilityRequirement)


def test_every_definition_uses_a_declared_application_namespace() -> None:
    for definition in _definitions():
        prefix = _ALLOWED_APPLICATION_PREFIXES[definition.application]
        assert definition.name.startswith(prefix)


def test_input_and_output_schemas_are_well_formed_object_schemas() -> None:
    for definition in _definitions():
        assert _schema_is_object(definition.input_schema), definition.name
        assert _schema_is_object(definition.output_schema), definition.name

        properties = definition.input_schema.get("properties", {})
        required = definition.input_schema.get("required", [])
        assert isinstance(required, list)
        assert len(set(required)) == len(required), definition.name
        for field in required:
            assert field in properties, (definition.name, field)


def test_registry_names_are_unique_and_deterministically_ordered() -> None:
    first = default_tool_registry().names()
    second = default_tool_registry().names()
    assert first == second
    assert len(set(first)) == len(first)


def test_snapshot_projects_every_definition_without_leaking_schemas() -> None:
    registry = default_tool_registry()
    snapshot = registry.snapshot()

    assert len(snapshot) == len(registry.names())
    assert tuple(row["name"] for row in snapshot) == registry.names()
    for row in snapshot:
        assert "input_schema" not in row
        assert "output_schema" not in row
        assert row["implementation_state"] in {state.value for state in ImplementationState}
        assert row["mutation_class"] in {cls.value for cls in MutationClass}


def test_registry_metadata_agrees_with_published_extended_manifest() -> None:
    registry = default_tool_registry()
    manifest = {
        tool["name"]: tool for tool in load_contract("extended_tool_manifest")["tools"]
    }

    assert set(manifest) == set(registry.names())
    for name, entry in manifest.items():
        definition = registry.get(name)
        assert entry["mutation_class"] == definition.mutation_class.value, name


def test_no_definition_overclaims_live_implementation_without_attestation() -> None:
    for definition in _definitions():
        assert definition.implementation_state is not ImplementationState.IMPLEMENTED_LIVE, (
            f"{definition.name} claims IMPLEMENTED_LIVE without live attestation evidence"
        )


def test_non_read_definitions_must_declare_a_read_back_strategy() -> None:
    for definition in _definitions():
        if definition.mutation_class is MutationClass.READ:
            continue
        assert definition.read_back_strategy != "NONE_READ_ONLY", definition.name


def test_registry_rejects_unknown_application_namespaces() -> None:
    template = default_tool_registry().get("planner_health")
    with pytest.raises(ValueError, match="unknown tool application"):
        ToolDefinition(
            name="teams_health",
            version=template.version,
            application="teams",
            surface=template.surface,
            domain=template.domain,
            input_schema=template.input_schema,
            output_schema=template.output_schema,
            mutation_class=template.mutation_class,
            risk_class=template.risk_class,
            implementation_state=template.implementation_state,
            capability_keys=(),
            ui_contract_dependencies=(),
            read_back_strategy=template.read_back_strategy,
            idempotency_semantics=template.idempotency_semantics,
            approval_requirement=template.approval_requirement,
            compatibility_requirement=template.compatibility_requirement,
        )
