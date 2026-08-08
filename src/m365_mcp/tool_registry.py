"""Canonical semantic Tool Registry for the M365 control plane.

CORE-008 establishes validated tool metadata as a product-level source of
truth. PLN-MIG-002 moves Planner-owned definitions out of this generic core;
the core retains only the application-neutral registry schema and composition.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from m365_mcp.application_registry import ApplicationKey


class MutationClass(StrEnum):
    """Closed semantic mutation classes used by policy/execution layers."""

    READ = "READ"
    CREATE = "CREATE"
    UPDATE = "UPDATE"
    DELETE = "DELETE"
    HIGH_IMPACT = "HIGH_IMPACT"


class ImplementationState(StrEnum):
    """Evidence-based implementation states required by the transition plan."""

    IMPLEMENTED_LIVE = "IMPLEMENTED_LIVE"
    IMPLEMENTED_MOCK_ONLY = "IMPLEMENTED_MOCK_ONLY"
    IMPLEMENTED_NOT_ATTESTED = "IMPLEMENTED_NOT_ATTESTED"
    SPECIFIED_ONLY = "SPECIFIED_ONLY"
    PLANNED = "PLANNED"
    DEPRECATED = "DEPRECATED"
    BLOCKED = "BLOCKED"


class CompatibilityRequirement(StrEnum):
    """Public compatibility disposition for a semantic tool."""

    PRESERVE = "PRESERVE"
    VERSION = "VERSION"
    DEPRECATE_LATER = "DEPRECATE_LATER"
    INTERNAL_ONLY = "INTERNAL_ONLY"


@dataclass(frozen=True)
class ToolDefinition:
    """Canonical metadata required to govern and project one semantic tool."""

    name: str
    version: str
    application: str
    surface: str
    domain: str
    input_schema: dict[str, Any]
    output_schema: dict[str, Any]
    mutation_class: MutationClass
    risk_class: str
    implementation_state: ImplementationState
    capability_keys: tuple[str, ...]
    ui_contract_dependencies: tuple[str, ...]
    read_back_strategy: str
    idempotency_semantics: str
    approval_requirement: str
    compatibility_requirement: CompatibilityRequirement

    def __post_init__(self) -> None:
        if not self.name or not self.version:
            raise ValueError("tool name and version are required")
        if self.application == "core":
            prefix = "m365_"
        elif self.application in {key.value for key in ApplicationKey}:
            prefix = f"{self.application}_"
        else:
            raise ValueError(f"unknown tool application: {self.application}")
        if not self.name.startswith(prefix):
            raise ValueError(
                f"tool name {self.name!r} does not match application prefix {prefix!r}"
            )
        if not self.surface.strip() or not self.domain.strip() or not self.risk_class.strip():
            raise ValueError("tool surface, domain and risk class are required")
        if self.input_schema.get("type") != "object":
            raise ValueError("tool input schema must be an object schema")
        if self.output_schema.get("type") != "object":
            raise ValueError("tool output schema must be an object schema")
        if not self.read_back_strategy or not self.idempotency_semantics:
            raise ValueError("read-back and idempotency semantics are required")
        if not self.approval_requirement:
            raise ValueError("approval requirement is required")


class ToolRegistry:
    """Immutable-by-interface validated registry of semantic tool definitions."""

    def __init__(self, definitions: tuple[ToolDefinition, ...]) -> None:
        by_name: dict[str, ToolDefinition] = {}
        for definition in definitions:
            if definition.name in by_name:
                raise ValueError(f"duplicate tool definition: {definition.name}")
            by_name[definition.name] = definition
        if not by_name:
            raise ValueError("tool registry must not be empty")
        self._definitions = by_name

    def get(self, name: str) -> ToolDefinition:
        """Return a definition by exact public semantic tool name."""
        return self._definitions[name]

    def names(self) -> tuple[str, ...]:
        """Return tool names in deterministic canonical order."""
        return tuple(self._definitions)

    def by_application(self, application: str) -> tuple[ToolDefinition, ...]:
        """Return definitions for one application/core scope."""
        return tuple(
            definition
            for definition in self._definitions.values()
            if definition.application == application
        )

    def snapshot(self) -> tuple[dict[str, object], ...]:
        """Return governance metadata without implementation callables or secrets."""
        return tuple(
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
            for definition in self._definitions.values()
        )


def default_tool_registry() -> ToolRegistry:
    """Compose the canonical registry from application-owned definitions."""
    from m365_mcp.apps.planner.tool_registry import planner_tool_definitions

    return ToolRegistry(planner_tool_definitions())


__all__ = [
    "CompatibilityRequirement",
    "ImplementationState",
    "MutationClass",
    "ToolDefinition",
    "ToolRegistry",
    "default_tool_registry",
]
