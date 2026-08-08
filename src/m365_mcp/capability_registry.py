"""Scoped capability definitions for the Microsoft 365 control plane.

CORE-011 introduces scope-aware capability identity only. PLN-MIG-003 moves
Planner-owned capability declarations out of this generic core while retaining
the application-neutral registry schema and composition boundary.
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
    """Closed deterministic registry of scoped capability definitions."""

    def __init__(self, definitions: tuple[ScopedCapability, ...]) -> None:
        by_identity: dict[tuple[str, str, str, str, str], ScopedCapability] = {}
        for definition in definitions:
            if definition.identity in by_identity:
                raise ValueError(f"duplicate scoped capability: {definition.identity!r}")
            by_identity[definition.identity] = definition
        if not by_identity:
            raise ValueError("capability registry must not be empty")
        self._definitions = by_identity

    def definitions(self) -> tuple[ScopedCapability, ...]:
        """Return definitions in deterministic insertion order."""
        return tuple(self._definitions.values())

    def by_application(self, application: str) -> tuple[ScopedCapability, ...]:
        """Return all definitions for one application."""
        return tuple(
            definition
            for definition in self._definitions.values()
            if definition.application == application
        )

    def capability_names(self, application: str) -> tuple[str, ...]:
        """Return deterministic unique semantic keys for an application."""
        return tuple(
            dict.fromkeys(
                definition.capability for definition in self.by_application(application)
            )
        )

    def has_capability(self, application: str, capability: str) -> bool:
        """Return whether the semantic capability exists in any declared scope."""
        return any(
            definition.capability == capability
            for definition in self.by_application(application)
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
        """Resolve one exact scoped definition, failing closed when absent."""
        return self._definitions[
            (application, surface, account_scope, container_scope, capability)
        ]

    def snapshot(self) -> tuple[dict[str, str], ...]:
        """Return scope-class metadata only; no tenant identifiers/content."""
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
    """Compose current scoped definitions from application-owned modules."""
    from m365_mcp.apps.planner.capability_registry import planner_capability_definitions

    return CapabilityRegistry(planner_capability_definitions())
