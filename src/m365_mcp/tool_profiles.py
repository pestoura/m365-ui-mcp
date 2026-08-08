"""Bounded semantic tool exposure profiles.

Profiles filter which already-governed semantic tools are exposed. They never
rewrite tool risk, policy, approval, idempotency or implementation metadata.
"""

from __future__ import annotations

from enum import StrEnum

from m365_mcp.tool_registry import MutationClass, ToolDefinition, ToolRegistry


class ToolProfile(StrEnum):
    """Closed public exposure profiles."""

    FULL = "full"
    PLANNER = "planner"
    OUTLOOK = "outlook"
    READ_ONLY = "read-only"


def project_tool_definitions(
    registry: ToolRegistry,
    profile: ToolProfile | str,
) -> tuple[ToolDefinition, ...]:
    """Return a deterministic exposure projection without mutating definitions."""
    selected = profile if isinstance(profile, ToolProfile) else ToolProfile(profile)
    definitions = tuple(registry.get(name) for name in registry.names())

    if selected is ToolProfile.FULL:
        return definitions
    if selected is ToolProfile.PLANNER:
        return tuple(item for item in definitions if item.application == "planner")
    if selected is ToolProfile.OUTLOOK:
        return tuple(item for item in definitions if item.application == "outlook")
    if selected is ToolProfile.READ_ONLY:
        return tuple(item for item in definitions if item.mutation_class is MutationClass.READ)
    raise AssertionError(f"unhandled tool profile: {selected}")
