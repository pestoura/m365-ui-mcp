"""Scoped capability definitions for the Microsoft 365 control plane.

CORE-011 introduces scope-aware capability identity only. Effective support is
computed later from auth/account/UI/runtime/policy evidence by CORE-012. Active
runtime definitions remain separate from reserved semantic declarations so a
future application can prepare contracts without being promoted for execution.
"""

from __future__ import annotations

from dataclasses import dataclass

from m365_mcp.application_registry import ApplicationKey


@dataclass(frozen=True)
class ScopedCapability:
    """One semantic capability bound to application and abstract scope classes."""

    application: str
    surface: str
    account_scope: str
    container_scope: str
    capability: str

    def __post_init__(self) -> None:
        if self.application not in {item.value for item in ApplicationKey}:
            raise ValueError(f"unknown capability application: {self.application}")
        for field_name in (
            "surface",
            "account_scope",
            "container_scope",
            "capability",
        ):
            value = getattr(self, field_name)
            if not value or value != value.strip() or any(char.isspace() for char in value):
                raise ValueError(f"invalid capability {field_name}: {value!r}")
        if "." not in self.capability:
            raise ValueError("capability key must be semantic namespace.action form")

    @property
    def identity(self) -> tuple[str, str, str, str, str]:
        """Return the complete stable scoped identity."""
        return (
            self.application,
            self.surface,
            self.account_scope,
            self.container_scope,
            self.capability,
        )


class CapabilityRegistry:
    """Deterministic active registry with optional reserved declarations."""

    def __init__(
        self,
        definitions: tuple[ScopedCapability, ...],
        *,
        reserved_definitions: tuple[ScopedCapability, ...] = (),
    ) -> None:
        by_identity: dict[tuple[str, str, str, str, str], ScopedCapability] = {}
        for definition in definitions:
            if definition.identity in by_identity:
                raise ValueError(f"duplicate scoped capability: {definition.identity!r}")
            by_identity[definition.identity] = definition
        if not by_identity:
            raise ValueError("capability registry must not be empty")

        declared_by_identity = dict(by_identity)
        for definition in reserved_definitions:
            if definition.identity in declared_by_identity:
                raise ValueError(
                    f"duplicate declared scoped capability: {definition.identity!r}"
                )
            declared_by_identity[definition.identity] = definition

        self._definitions = by_identity
        self._declared_definitions = declared_by_identity

    def definitions(self) -> tuple[ScopedCapability, ...]:
        """Return active runtime definitions in deterministic insertion order."""
        return tuple(self._definitions.values())

    def declared_definitions(self) -> tuple[ScopedCapability, ...]:
        """Return active plus reserved semantic declarations."""
        return tuple(self._declared_definitions.values())

    def by_application(self, application: str) -> tuple[ScopedCapability, ...]:
        """Return active runtime definitions for one application."""
        return tuple(
            definition
            for definition in self._definitions.values()
            if definition.application == application
        )

    def declared_by_application(self, application: str) -> tuple[ScopedCapability, ...]:
        """Return active plus reserved declarations for one application."""
        return tuple(
            definition
            for definition in self._declared_definitions.values()
            if definition.application == application
        )

    def capability_names(self, application: str) -> tuple[str, ...]:
        """Return deterministic active semantic keys for an application."""
        return tuple(
            dict.fromkeys(
                definition.capability for definition in self.by_application(application)
            )
        )

    def declared_capability_names(self, application: str) -> tuple[str, ...]:
        """Return deterministic active plus reserved semantic keys."""
        return tuple(
            dict.fromkeys(
                definition.capability
                for definition in self.declared_by_application(application)
            )
        )

    def has_capability(self, application: str, capability: str) -> bool:
        """Return whether a semantic capability is declared in any scope."""
        return any(
            definition.capability == capability
            for definition in self.declared_by_application(application)
        )

    def get_scoped(
        self,
        *,
        application: str,
        surface: str,
        account_scope: str,
        container_scope: str,
        capability: str,
    ) -> ScopedCapability:
        """Resolve one active exact scoped definition, failing closed when absent."""
        return self._definitions[
            (application, surface, account_scope, container_scope, capability)
        ]

    def snapshot(self) -> tuple[dict[str, str], ...]:
        """Return active scope-class metadata only; no tenant identifiers/content."""
        return tuple(
            {
                "application": definition.application,
                "surface": definition.surface,
                "account_scope": definition.account_scope,
                "container_scope": definition.container_scope,
                "capability": definition.capability,
            }
            for definition in self._definitions.values()
        )


def default_capability_registry() -> CapabilityRegistry:
    """Compose active definitions plus reserved semantic declarations."""
    from m365_mcp.apps.outlook.capability_registry import outlook_capability_definitions
    from m365_mcp.apps.planner.capability_registry import planner_capability_definitions

    return CapabilityRegistry(
        planner_capability_definitions(),
        reserved_definitions=outlook_capability_definitions(),
    )
