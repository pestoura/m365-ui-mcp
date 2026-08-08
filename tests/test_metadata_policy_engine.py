"""CORE-031 metadata-driven policy engine tests."""

from __future__ import annotations

from types import SimpleNamespace
from typing import cast

from m365_mcp.config import Settings
from m365_mcp.policy import READ_TOOLS, Decision, MetadataPolicyEngine, evaluate
from m365_mcp.tool_registry import (
    CompatibilityRequirement,
    ImplementationState,
    MutationClass,
    ToolDefinition,
    ToolRegistry,
    default_tool_registry,
)


def _definition(name: str, mutation_class: MutationClass) -> ToolDefinition:
    return ToolDefinition(
        name=name,
        version="test",
        application="core",
        surface="test",
        domain="test",
        input_schema={"type": "object", "properties": {}, "additionalProperties": False},
        output_schema={"type": "object", "properties": {}},
        mutation_class=mutation_class,
        risk_class="READ_ONLY",
        implementation_state=ImplementationState.SPECIFIED_ONLY,
        capability_keys=("test.capability",),
        ui_contract_dependencies=(),
        read_back_strategy="TEST_READ_BACK",
        idempotency_semantics="test",
        approval_requirement="none",
        compatibility_requirement=CompatibilityRequirement.INTERNAL_ONLY,
    )


def test_legacy_read_tool_set_is_derived_from_registry_metadata() -> None:
    registry = default_tool_registry()
    expected = frozenset(
        definition.name
        for definition in registry.by_application("planner")
        if definition.mutation_class is MutationClass.READ
    )
    assert READ_TOOLS == expected
    assert len(READ_TOOLS) == 17


def test_registered_read_tool_is_allowed_without_name_allowlist() -> None:
    registry = ToolRegistry((_definition("m365_test_read", MutationClass.READ),))
    result = MetadataPolicyEngine(registry).evaluate("m365_test_read", Settings())

    assert result.decision is Decision.ALLOW
    assert result.reason == "REGISTERED_READ_TOOL"
    assert result.tool == "m365_test_read"
    assert result.application == "core"
    assert result.mutation_class is MutationClass.READ
    assert result.capability_keys == ("test.capability",)


def test_registered_mutation_is_denied_from_metadata_when_mutations_disabled() -> None:
    registry = ToolRegistry((_definition("m365_test_update", MutationClass.UPDATE),))
    result = MetadataPolicyEngine(registry).evaluate("m365_test_update", Settings())

    assert result.decision is Decision.DENY
    assert result.reason == "MUTATIONS_DISABLED_IN_0_1_0"
    assert result.mutation_class is MutationClass.UPDATE


def test_registered_mutation_requires_approval_when_runtime_allows_mutations() -> None:
    registry = ToolRegistry((_definition("m365_test_update", MutationClass.UPDATE),))
    permissive = cast(Settings, SimpleNamespace(allow_mutations=True))
    result = MetadataPolicyEngine(registry).evaluate("m365_test_update", permissive)

    assert result.decision is Decision.REQUIRE_APPROVAL
    assert result.reason == "MUTATION_REQUIRES_APPROVAL"


def test_unknown_tool_is_always_denied_even_if_mutations_are_permitted() -> None:
    permissive = cast(Settings, SimpleNamespace(allow_mutations=True))
    result = MetadataPolicyEngine().evaluate("planner_unregistered_action", permissive)

    assert result.decision is Decision.DENY
    assert result.reason == "TOOL_NOT_REGISTERED"


def test_compatibility_mutation_override_can_only_make_policy_stricter() -> None:
    result = evaluate("planner_plan_list", Settings(), mutation=True)
    assert result.decision is Decision.DENY
    assert result.reason == "MUTATIONS_DISABLED_IN_0_1_0"
