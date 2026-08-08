"""Closed security-tier model for semantic M365 operations.

CORE-032 introduces a bounded T0..T4 classification derived from canonical
Tool Registry metadata. The model is deliberately conservative: unknown risk
classes fail into the highest tier and classification can never make an
existing policy decision less restrictive.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum

from m365_mcp.tool_registry import MutationClass, ToolDefinition


class SecurityTier(IntEnum):
    """Closed operation security tiers, ordered from least to most sensitive."""

    T0 = 0  # local/product metadata; no authenticated tenant content
    T1 = 1  # session/runtime/account-state observation or interaction
    T2 = 2  # authenticated Microsoft 365 content reads
    T3 = 3  # bounded/reversible mutations
    T4 = 4  # destructive, externally visible, or otherwise high-impact mutations


@dataclass(frozen=True)
class SecurityTierAssessment:
    """Sanitized explanation of one deterministic tier classification."""

    tier: SecurityTier
    reason: str


_T0_RISK_CLASSES = frozenset({"READ_ONLY"})
_T1_RISK_CLASSES = frozenset(
    {
        "SESSION_OBSERVATION",
        "SESSION_INTERACTION",
        "SESSION_METADATA",
        "ACCOUNT_CONTEXT_READ",
    }
)
_T2_RISK_CLASSES = frozenset({"M365_CONTENT_READ"})


def classify_security_tier(definition: ToolDefinition) -> SecurityTierAssessment:
    """Classify one semantic tool using only canonical registry metadata.

    Mutation class dominates read risk metadata. Unknown read risk classes fail
    closed into T4 so adding a new semantic risk vocabulary cannot silently
    inherit a lower-privilege tier.
    """
    if definition.mutation_class in {MutationClass.DELETE, MutationClass.HIGH_IMPACT}:
        return SecurityTierAssessment(SecurityTier.T4, "DESTRUCTIVE_OR_HIGH_IMPACT_MUTATION")

    if definition.mutation_class in {MutationClass.CREATE, MutationClass.UPDATE}:
        return SecurityTierAssessment(SecurityTier.T3, "BOUNDED_MUTATION")

    if definition.risk_class in _T0_RISK_CLASSES:
        return SecurityTierAssessment(SecurityTier.T0, "LOCAL_OR_PRODUCT_METADATA_READ")

    if definition.risk_class in _T1_RISK_CLASSES:
        return SecurityTierAssessment(SecurityTier.T1, "SESSION_OR_ACCOUNT_CONTEXT")

    if definition.risk_class in _T2_RISK_CLASSES:
        return SecurityTierAssessment(SecurityTier.T2, "AUTHENTICATED_M365_CONTENT_READ")

    return SecurityTierAssessment(SecurityTier.T4, "UNCLASSIFIED_RISK_FAIL_CLOSED")


__all__ = ["SecurityTier", "SecurityTierAssessment", "classify_security_tier"]
