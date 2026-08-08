from dataclasses import replace

import pytest

import m365_mcp.compensation_registry as compensation_registry
import m365_mcp.tool_registry as tool_registry


def _first_tool(registry: tool_registry.ToolRegistry) -> tool_registry.ToolDefinition:
    return registry.get(registry.names()[0])


def _mutation_tool(
    mutation_class: tool_registry.MutationClass = tool_registry.MutationClass.CREATE,
) -> tool_registry.ToolDefinition:
    source = _first_tool(tool_registry.default_tool_registry())
    return replace(
        source,
        name="planner_synthetic_mutation",
        mutation_class=mutation_class,
        approval_requirement="required",
    )


def test_current_read_only_registry_has_explicitly_empty_compensation_set() -> None:
    registry = compensation_registry.default_compensation_registry()
    tools = tool_registry.default_tool_registry()

    assert registry.definitions() == ()
    registry.validate_tool_registry_coverage(tools)
    assert all(
        tools.get(name).mutation_class is tool_registry.MutationClass.READ
        for name in tools.names()
    )


def test_every_registered_mutation_requires_explicit_compensation_definition() -> None:
    mutation = _mutation_tool()
    tools = tool_registry.ToolRegistry((mutation,))
    registry = compensation_registry.CompensationRegistry(())

    with pytest.raises(ValueError, match="compensation definition is missing"):
        registry.validate_tool_registry_coverage(tools)


def test_automatic_compensation_binds_exact_tool_version_and_mutation_class() -> None:
    mutation = _mutation_tool(tool_registry.MutationClass.CREATE)
    definition = compensation_registry.CompensationDefinition(
        tool_name=mutation.name,
        tool_version=mutation.version,
        mutation_class=mutation.mutation_class,
        availability=compensation_registry.CompensationAvailability.AUTOMATIC,
        strategy=compensation_registry.CompensationStrategy.DELETE_CREATED_RESOURCE,
    )
    registry = compensation_registry.CompensationRegistry((definition,))

    registry.validate_tool_registry_coverage(tool_registry.ToolRegistry((mutation,)))
    resolved = registry.for_tool(mutation)
    assert resolved is definition
    assert resolved.available is True
    assert resolved.automatic is True
    assert resolved.requires_checkpoint is True


def test_manual_only_and_unavailable_strategies_are_explicit() -> None:
    mutation = _mutation_tool(tool_registry.MutationClass.UPDATE)
    manual = compensation_registry.CompensationDefinition(
        tool_name=mutation.name,
        tool_version=mutation.version,
        mutation_class=mutation.mutation_class,
        availability=compensation_registry.CompensationAvailability.MANUAL_ONLY,
        strategy=compensation_registry.CompensationStrategy.MANUAL_RECONCILIATION,
    )
    unavailable = compensation_registry.CompensationDefinition(
        tool_name="synthetic_delete",
        tool_version=mutation.version,
        mutation_class=tool_registry.MutationClass.DELETE,
        availability=compensation_registry.CompensationAvailability.UNAVAILABLE,
        strategy=compensation_registry.CompensationStrategy.NONE,
    )

    assert manual.available is True
    assert manual.automatic is False
    assert unavailable.available is False
    assert unavailable.automatic is False


def test_invalid_availability_strategy_combinations_fail_closed() -> None:
    mutation = _mutation_tool()

    with pytest.raises(ValueError, match="automatic compensation requires"):
        compensation_registry.CompensationDefinition(
            tool_name=mutation.name,
            tool_version=mutation.version,
            mutation_class=mutation.mutation_class,
            availability=compensation_registry.CompensationAvailability.AUTOMATIC,
            strategy=compensation_registry.CompensationStrategy.NONE,
        )

    with pytest.raises(ValueError, match="manual-only compensation requires"):
        compensation_registry.CompensationDefinition(
            tool_name=mutation.name,
            tool_version=mutation.version,
            mutation_class=mutation.mutation_class,
            availability=compensation_registry.CompensationAvailability.MANUAL_ONLY,
            strategy=compensation_registry.CompensationStrategy.INVERSE_OPERATION,
        )

    with pytest.raises(ValueError, match="unavailable compensation must use NONE"):
        compensation_registry.CompensationDefinition(
            tool_name=mutation.name,
            tool_version=mutation.version,
            mutation_class=mutation.mutation_class,
            availability=compensation_registry.CompensationAvailability.UNAVAILABLE,
            strategy=compensation_registry.CompensationStrategy.RESTORE_PREVIOUS_STATE,
        )


def test_read_tools_cannot_declare_compensation() -> None:
    read_tool = _first_tool(tool_registry.default_tool_registry())

    with pytest.raises(ValueError, match="read-only tools cannot declare"):
        compensation_registry.CompensationDefinition(
            tool_name=read_tool.name,
            tool_version=read_tool.version,
            mutation_class=read_tool.mutation_class,
            availability=compensation_registry.CompensationAvailability.UNAVAILABLE,
            strategy=compensation_registry.CompensationStrategy.NONE,
        )


def test_version_or_mutation_class_drift_fails_closed() -> None:
    mutation = _mutation_tool(tool_registry.MutationClass.UPDATE)
    wrong_version = compensation_registry.CompensationDefinition(
        tool_name=mutation.name,
        tool_version="9.9.9",
        mutation_class=mutation.mutation_class,
        availability=compensation_registry.CompensationAvailability.AUTOMATIC,
        strategy=compensation_registry.CompensationStrategy.RESTORE_PREVIOUS_STATE,
    )
    wrong_class = compensation_registry.CompensationDefinition(
        tool_name=mutation.name,
        tool_version=mutation.version,
        mutation_class=tool_registry.MutationClass.DELETE,
        availability=compensation_registry.CompensationAvailability.MANUAL_ONLY,
        strategy=compensation_registry.CompensationStrategy.MANUAL_RECONCILIATION,
    )

    with pytest.raises(ValueError):
        registry = compensation_registry.CompensationRegistry((wrong_version,))
        registry.validate_tool_registry_coverage(tool_registry.ToolRegistry((mutation,)))
    with pytest.raises(ValueError, match="mutation class"):
        compensation_registry.CompensationRegistry((wrong_class,)).for_tool(mutation)


def test_orphan_compensation_definition_is_rejected() -> None:
    mutation = _mutation_tool()
    definition = compensation_registry.CompensationDefinition(
        tool_name=mutation.name,
        tool_version=mutation.version,
        mutation_class=mutation.mutation_class,
        availability=compensation_registry.CompensationAvailability.MANUAL_ONLY,
        strategy=compensation_registry.CompensationStrategy.MANUAL_RECONCILIATION,
    )

    with pytest.raises(ValueError, match="orphan compensation definition"):
        registry = compensation_registry.CompensationRegistry((definition,))
        registry.validate_tool_registry_coverage(tool_registry.default_tool_registry())
