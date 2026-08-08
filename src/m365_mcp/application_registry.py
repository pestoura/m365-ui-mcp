"""Closed, validated Microsoft 365 application registry.

The registry is explicit by construction: applications cannot self-register via
entry points, filesystem discovery or import side effects. An application only
becomes executable when the composition root supplies a validated semantic
registrar.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from m365_mcp.config import Settings
from m365_mcp.control_plane import ToolRegistrar


class ApplicationKey(StrEnum):
    """Stable application identifiers used by the M365 control plane."""

    PLANNER = "planner"
    OUTLOOK = "outlook"


class ApplicationState(StrEnum):
    """Execution state of an application registration."""

    ENABLED = "ENABLED"
    RESERVED = "RESERVED"


@dataclass(frozen=True)
class ApplicationRegistration:
    """Validated application metadata and optional semantic registrar."""

    key: ApplicationKey
    state: ApplicationState
    capability_namespace: str
    registrar: ToolRegistrar | None = None

    def __post_init__(self) -> None:
        namespace = self.capability_namespace.strip()
        if not namespace:
            raise ValueError("application capability namespace must not be empty")
        if self.state is ApplicationState.ENABLED and self.registrar is None:
            raise ValueError("enabled application requires a semantic registrar")
        if self.state is ApplicationState.RESERVED and self.registrar is not None:
            raise ValueError("reserved application must not expose a registrar")


class ApplicationRegistry:
    """Immutable closed registry used by the composition root."""

    def __init__(self, registrations: tuple[ApplicationRegistration, ...]) -> None:
        by_key: dict[ApplicationKey, ApplicationRegistration] = {}
        for registration in registrations:
            if registration.key in by_key:
                raise ValueError(f"duplicate application registration: {registration.key}")
            by_key[registration.key] = registration
        if not by_key:
            raise ValueError("application registry must not be empty")
        self._registrations = by_key

    def get(self, key: ApplicationKey) -> ApplicationRegistration:
        """Return a registration by stable application key."""
        return self._registrations[key]

    def keys(self) -> tuple[ApplicationKey, ...]:
        """Return registered keys in deterministic insertion order."""
        return tuple(self._registrations)

    def enabled(self) -> tuple[ApplicationRegistration, ...]:
        """Return only executable application registrations."""
        return tuple(
            registration
            for registration in self._registrations.values()
            if registration.state is ApplicationState.ENABLED
        )

    def register_enabled_tools(self, server: Any, settings: Settings) -> None:
        """Project tools only from explicitly enabled validated registrars."""
        for registration in self.enabled():
            registrar = registration.registrar
            if registrar is None:  # defensive invariant; constructor rejects this state
                raise RuntimeError(f"enabled application has no registrar: {registration.key}")
            registrar(server, settings)

    def snapshot(self) -> tuple[dict[str, str], ...]:
        """Return non-secret registry metadata for evidence/tests."""
        return tuple(
            {
                "application": registration.key.value,
                "state": registration.state.value,
                "capability_namespace": registration.capability_namespace,
            }
            for registration in self._registrations.values()
        )


def default_application_registry() -> ApplicationRegistry:
    """Build the explicit product registry for the current migration phase.

    Outlook is deliberately RESERVED until Planner parity is GREEN and the
    ordered Outlook phase starts. It is therefore known to the core but cannot
    register tools or execute browser operations yet.
    """
    from planner_mcp.registration import register_planner_tools

    return ApplicationRegistry(
        (
            ApplicationRegistration(
                key=ApplicationKey.PLANNER,
                state=ApplicationState.ENABLED,
                capability_namespace="planner",
                registrar=register_planner_tools,
            ),
            ApplicationRegistration(
                key=ApplicationKey.OUTLOOK,
                state=ApplicationState.RESERVED,
                capability_namespace="outlook",
            ),
        )
    )
