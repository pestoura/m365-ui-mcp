"""Application-neutral metadata-driven policy engine.

CORE-031 removes hard-coded semantic tool-name allowlists from policy
evaluation. Decisions are derived from canonical Tool Registry metadata and
runtime mutation settings. Security tiers and scope-aware constraints are
introduced separately by CORE-032/033.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from m365_mcp.config import Settings
from m365_mcp.tool_registry import MutationClass, ToolDefinition, ToolRegistry, default_tool_registry


class Decision(StrEnum):
    """Closed policy decisions."""

    ALLOW = "ALLOW"
    DENY = "DENY"
    REQUIRE_APPROVAL = "REQUIRE_APPROVAL"


@dataclass(frozen=True)
class PolicyResult:
    """Policy decision with bounded registry-derived context."""

    decision: Decision
    reason: str
    tool: str | None = None
    application: str | None = None
    mutation_class: MutationClass | None = None
    capability_keys: tuple[str, ...] = ()

    @property
    def allowed(self) -> bool:
        return self.decision is Decision.ALLOW


class MetadataPolicyEngine:
    """Evaluate semantic tools solely from canonical Tool Registry metadata."""

    def __init__(self, registry: ToolRegistry | None = None) -> None:
        self.registry = registry or default_tool_registry()

    def evaluate(
        self,
        tool: str,
        settings: Settings,
        *,
        mutation: bool = False,
    ) -> PolicyResult:
        """Evaluate one registered semantic tool and fail closed on unknown names.

        ``mutation`` is retained only as a compatibility safety override. It can
        make evaluation stricter but cannot convert registry mutation metadata
        into a read or authorize an unregistered tool.
        """
        try:
            definition = self.registry.get(tool)
        except KeyError:
            return PolicyResult(Decision.DENY, "TOOL_NOT_REGISTERED", tool=tool)

        metadata_mutation = definition.mutation_class is not MutationClass.READ
        mutation_requested = metadata_mutation or mutation

        if mutation_requested and not settings.allow_mutations:
            return self._result(
                definition,
                Decision.DENY,
                "MUTATIONS_DISABLED_IN_0_1_0",
            )

        if mutation_requested or definition.approval_requirement != "none":
            return self._result(
                definition,
                Decision.REQUIRE_APPROVAL,
                "MUTATION_REQUIRES_APPROVAL",
            )

        return self._result(definition, Decision.ALLOW, "REGISTERED_READ_TOOL")

    @staticmethod
    def _result(
        definition: ToolDefinition,
        decision: Decision,
        reason: str,
    ) -> PolicyResult:
        return PolicyResult(
            decision=decision,
            reason=reason,
            tool=definition.name,
            application=definition.application,
            mutation_class=definition.mutation_class,
            capability_keys=definition.capability_keys,
        )


def evaluate(
    tool: str,
    settings: Settings,
    *,
    mutation: bool = False,
    registry: ToolRegistry | None = None,
) -> PolicyResult:
    """Compatibility function backed by the metadata-driven engine."""
    return MetadataPolicyEngine(registry).evaluate(tool, settings, mutation=mutation)


READ_TOOLS = frozenset(
    definition.name
    for definition in default_tool_registry().by_application("planner")
    if definition.mutation_class is MutationClass.READ
)


__all__ = [
    "Decision",
    "MetadataPolicyEngine",
    "PolicyResult",
    "READ_TOOLS",
    "evaluate",
]
