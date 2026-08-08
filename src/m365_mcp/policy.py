"""Application-neutral metadata-driven policy engine.

CORE-031 removes hard-coded semantic tool-name allowlists from policy
evaluation. CORE-032 adds a closed T0..T4 security-tier projection derived
from the same canonical metadata. CORE-033 makes sanitized application,
mailbox and resource scope a first-class policy input and result.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from m365_mcp.capability_registry import CapabilityRegistry, default_capability_registry
from m365_mcp.config import Settings
from m365_mcp.policy_scope import PolicyScope, assess_policy_scope
from m365_mcp.security_tiers import SecurityTier, classify_security_tier
from m365_mcp.tool_registry import (
    MutationClass,
    ToolDefinition,
    ToolRegistry,
    default_tool_registry,
)


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
    security_tier: SecurityTier | None = None
    capability_keys: tuple[str, ...] = ()
    scope: PolicyScope | None = None
    scope_reason: str | None = None
    scope_derived: bool = False

    @property
    def allowed(self) -> bool:
        return self.decision is Decision.ALLOW


class MetadataPolicyEngine:
    """Evaluate semantic tools solely from canonical reviewed metadata."""

    def __init__(
        self,
        registry: ToolRegistry | None = None,
        capability_registry: CapabilityRegistry | None = None,
    ) -> None:
        self.registry = registry or default_tool_registry()
        self.capability_registry = capability_registry or default_capability_registry()

    def evaluate(
        self,
        tool: str,
        settings: Settings,
        *,
        mutation: bool = False,
        scope: PolicyScope | None = None,
    ) -> PolicyResult:
        """Evaluate one semantic tool and fail closed on unknown names/scopes.

        ``mutation`` is retained only as a compatibility safety override. It can
        make evaluation stricter but cannot convert registry mutation metadata
        into a read or authorize an unregistered tool.

        ``scope`` is explicit when callers already have a bounded execution
        scope. For the preserved 0.1 Planner surface, omission derives the exact
        canonical semantic scope from reviewed Tool/Capability Registry metadata
        so CORE-033 does not create a compatibility break.
        """
        try:
            definition = self.registry.get(tool)
        except KeyError:
            return PolicyResult(Decision.DENY, "TOOL_NOT_REGISTERED", tool=tool)

        tier = classify_security_tier(definition).tier
        try:
            scope_assessment = assess_policy_scope(
                definition,
                scope,
                self.capability_registry,
            )
        except ValueError:
            return self._result(
                definition,
                Decision.DENY,
                "SCOPE_METADATA_INVALID",
                tier,
            )

        if not scope_assessment.allowed:
            return self._result(
                definition,
                Decision.DENY,
                scope_assessment.reason,
                tier,
                scope=scope_assessment.effective_scope,
                scope_reason=scope_assessment.reason,
                scope_derived=False,
            )

        metadata_mutation = definition.mutation_class is not MutationClass.READ
        mutation_requested = metadata_mutation or mutation

        if mutation_requested and not settings.allow_mutations:
            return self._result(
                definition,
                Decision.DENY,
                "MUTATIONS_DISABLED_IN_0_1_0",
                tier,
                scope=scope_assessment.effective_scope,
                scope_reason=scope_assessment.reason,
                scope_derived=scope_assessment.derived,
            )

        if (
            tier >= SecurityTier.T3
            or mutation_requested
            or definition.approval_requirement != "none"
        ):
            return self._result(
                definition,
                Decision.REQUIRE_APPROVAL,
                "MUTATION_REQUIRES_APPROVAL",
                tier,
                scope=scope_assessment.effective_scope,
                scope_reason=scope_assessment.reason,
                scope_derived=scope_assessment.derived,
            )

        return self._result(
            definition,
            Decision.ALLOW,
            "REGISTERED_READ_TOOL",
            tier,
            scope=scope_assessment.effective_scope,
            scope_reason=scope_assessment.reason,
            scope_derived=scope_assessment.derived,
        )

    @staticmethod
    def _result(
        definition: ToolDefinition,
        decision: Decision,
        reason: str,
        security_tier: SecurityTier,
        *,
        scope: PolicyScope | None = None,
        scope_reason: str | None = None,
        scope_derived: bool = False,
    ) -> PolicyResult:
        return PolicyResult(
            decision=decision,
            reason=reason,
            tool=definition.name,
            application=definition.application,
            mutation_class=definition.mutation_class,
            security_tier=security_tier,
            capability_keys=definition.capability_keys,
            scope=scope,
            scope_reason=scope_reason,
            scope_derived=scope_derived,
        )


def evaluate(
    tool: str,
    settings: Settings,
    *,
    mutation: bool = False,
    scope: PolicyScope | None = None,
    registry: ToolRegistry | None = None,
    capability_registry: CapabilityRegistry | None = None,
) -> PolicyResult:
    """Compatibility function backed by the metadata-driven engine."""
    return MetadataPolicyEngine(registry, capability_registry).evaluate(
        tool,
        settings,
        mutation=mutation,
        scope=scope,
    )


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
