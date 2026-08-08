"""Scoped capability definitions for the Microsoft 365 control plane.

CORE-011 introduces scope-aware capability identity only. Effective support is
computed later from auth/account/UI/runtime/policy evidence by CORE-012; this
registry therefore contains no tenant content and makes no live-support claim.
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


def _planner_capability(capability: str, container_scope: str) -> ScopedCapability:
    return ScopedCapability(
        application=ApplicationKey.PLANNER.value,
        surface="planner_web",
        account_scope="professional_session",
        container_scope=container_scope,
        capability=capability,
    )


def default_capability_registry() -> CapabilityRegistry:
    """Return current scoped definitions without overstating live support."""
    return CapabilityRegistry(
        (
            _planner_capability("plans.read", "account"),
            _planner_capability("tasks.read", "plan"),
            _planner_capability("buckets.read", "plan"),
            _planner_capability("dependencies.read", "plan"),
            _planner_capability("scheduling.read", "plan"),
            _planner_capability("goals.read", "plan"),
            _planner_capability("sprints.read", "plan"),
            _planner_capability("resources.read", "plan"),
            _planner_capability("custom_fields.read", "plan"),
            _planner_capability("portfolios.read", "account"),
            _planner_capability("project_snapshot.read", "plan"),
        )
    )
