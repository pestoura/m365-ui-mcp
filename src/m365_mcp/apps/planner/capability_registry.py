"""Planner-owned scoped capability definitions for PLN-MIG-003."""

from __future__ import annotations

from m365_mcp.application_registry import ApplicationKey
from m365_mcp.capability_registry import ScopedCapability


def _planner_capability(capability: str, container_scope: str) -> ScopedCapability:
    return ScopedCapability(
        application=ApplicationKey.PLANNER.value,
        surface="planner_web",
        account_scope="professional_session",
        container_scope=container_scope,
        capability=capability,
    )


def planner_capability_definitions() -> tuple[ScopedCapability, ...]:
    """Return the 11 preserved Planner capability definitions in canonical order."""
    return (
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


__all__ = ["planner_capability_definitions"]
