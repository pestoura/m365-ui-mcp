"""Explicit mutation compensation metadata for CORE-041.

Every registered mutation must declare whether compensation is automatic,
manual-only, or unavailable and must bind that declaration to the exact tool
version and mutation class. Current public 0.1.0 tools are read-only, so the
default registry is intentionally empty but fully coverage-validated.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from m365_mcp.tool_registry import MutationClass, ToolDefinition, ToolRegistry


class CompensationAvailability(StrEnum):
    """Closed compensation availability classes."""

    AUTOMATIC = "AUTOMATIC"
    MANUAL_ONLY = "MANUAL_ONLY"
    UNAVAILABLE = "UNAVAILABLE"


class CompensationStrategy(StrEnum):
    """Closed strategy vocabulary; application-specific execution comes later."""

    DELETE_CREATED_RESOURCE = "DELETE_CREATED_RESOURCE"
    RESTORE_PREVIOUS_STATE = "RESTORE_PREVIOUS_STATE"
    INVERSE_OPERATION = "INVERSE_OPERATION"
    MANUAL_RECONCILIATION = "MANUAL_RECONCILIATION"
    NONE = "NONE"


_AUTOMATIC_STRATEGIES = frozenset(
    {
        CompensationStrategy.DELETE_CREATED_RESOURCE,
        CompensationStrategy.RESTORE_PREVIOUS_STATE,
        CompensationStrategy.INVERSE_OPERATION,
    }
)


@dataclass(frozen=True)
class CompensationDefinition:
    """Version-bound compensation declaration for one semantic mutation tool."""

    tool_name: str
    tool_version: str
    mutation_class: MutationClass
    availability: CompensationAvailability
    strategy: CompensationStrategy
    requires_checkpoint: bool = True

    def __post_init__(self) -> None:
        if not self.tool_name.strip() or any(char.isspace() for char in self.tool_name):
            raise ValueError("compensation tool_name must be a semantic token")
        if not self.tool_version.strip():
            raise ValueError("compensation tool_version must not be empty")
        if self.mutation_class is MutationClass.READ:
            raise ValueError("read-only tools cannot declare mutation compensation")
        if self.availability is CompensationAvailability.AUTOMATIC:
            if self.strategy not in _AUTOMATIC_STRATEGIES:
                raise ValueError("automatic compensation requires an automatic strategy")
        elif self.availability is CompensationAvailability.MANUAL_ONLY:
            if self.strategy is not CompensationStrategy.MANUAL_RECONCILIATION:
                raise ValueError("manual-only compensation requires manual reconciliation")
        elif self.strategy is not CompensationStrategy.NONE:
            raise ValueError("unavailable compensation must use NONE strategy")

    @property
    def automatic(self) -> bool:
        return self.availability is CompensationAvailability.AUTOMATIC

    @property
    def available(self) -> bool:
        return self.availability is not CompensationAvailability.UNAVAILABLE

    @property
    def identity(self) -> tuple[str, str]:
        return (self.tool_name, self.tool_version)


class CompensationRegistry:
    """Deterministic registry requiring explicit coverage for every mutation."""

    def __init__(self, definitions: tuple[CompensationDefinition, ...]) -> None:
        by_identity: dict[tuple[str, str], CompensationDefinition] = {}
        for definition in definitions:
            if definition.identity in by_identity:
                raise ValueError(f"duplicate compensation definition: {definition.identity!r}")
            by_identity[definition.identity] = definition
        self._definitions = by_identity

    def definitions(self) -> tuple[CompensationDefinition, ...]:
        return tuple(self._definitions.values())

    def for_tool(self, tool: ToolDefinition) -> CompensationDefinition:
        """Resolve exact version/class compensation metadata or fail closed."""
        if tool.mutation_class is MutationClass.READ:
            raise ValueError("read-only tool has no mutation compensation")
        try:
            definition = self._definitions[(tool.name, tool.version)]
        except KeyError as exc:
            raise ValueError("mutation compensation definition is missing") from exc
        if definition.mutation_class is not tool.mutation_class:
            raise ValueError("compensation mutation class does not match Tool Registry")
        return definition

    def validate_tool_registry_coverage(self, tools: ToolRegistry) -> None:
        """Require exact compensation metadata for every registered mutation.

        Orphan definitions are rejected as well so removed/renamed mutations
        cannot leave stale compensation declarations that appear supported.
        """
        registered = {(tool.name, tool.version): tool for tool in tools.definitions()}
        for tool in tools.definitions():
            if tool.mutation_class is not MutationClass.READ:
                self.for_tool(tool)
        for identity, definition in self._definitions.items():
            tool = registered.get(identity)
            if tool is None:
                raise ValueError("orphan compensation definition")
            if tool.mutation_class is MutationClass.READ:
                raise ValueError("compensation definition targets read-only tool")
            if tool.mutation_class is not definition.mutation_class:
                raise ValueError("compensation mutation class does not match Tool Registry")


def default_compensation_registry() -> CompensationRegistry:
    """Return explicit current compensation metadata.

    The public 0.1.0 Tool Registry currently exposes no mutations, therefore
    the correct explicit compensation set is empty until a governed mutation is
    registered by a later roadmap phase.
    """
    return CompensationRegistry(())


__all__ = [
    "CompensationAvailability",
    "CompensationDefinition",
    "CompensationRegistry",
    "CompensationStrategy",
    "default_compensation_registry",
]
