"""Effective capability projection from registry definitions plus runtime evidence.

A registry declaration never implies support by itself. CORE-012 requires all
relevant evidence dimensions to be evaluated before a capability may be
promoted to READ_SUPPORTED.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from m365_mcp.capability_registry import CapabilityRegistry, ScopedCapability


class EffectiveCapabilityState(StrEnum):
    """Evidence-derived states aligned with the existing Planner vocabulary."""

    UNVERIFIED_LIVE = "UNVERIFIED_LIVE"
    DISCOVERED = "DISCOVERED"
    READ_SUPPORTED = "READ_SUPPORTED"
    MUTATION_SUPPORTED = "MUTATION_SUPPORTED"
    DEGRADED = "DEGRADED"
    BLOCKED = "BLOCKED"
    OUT_OF_SCOPE = "OUT_OF_SCOPE"


@dataclass(frozen=True)
class EffectiveCapabilityEvidence:
    """Sanitized evidence dimensions used to compute effective support."""

    authenticated: bool
    account_context_valid: bool
    ui_attested: bool
    runtime_healthy: bool
    policy_allowed: bool
    license_available: bool
    live_evidence: bool


@dataclass(frozen=True)
class EffectiveCapability:
    """One scoped capability plus its computed support state and reason codes."""

    definition: ScopedCapability
    state: EffectiveCapabilityState
    reasons: tuple[str, ...]
    evidence: EffectiveCapabilityEvidence

    @property
    def supported(self) -> bool:
        return self.state in {
            EffectiveCapabilityState.READ_SUPPORTED,
            EffectiveCapabilityState.MUTATION_SUPPORTED,
        }

    def to_dict(self) -> dict[str, object]:
        return {
            "application": self.definition.application,
            "surface": self.definition.surface,
            "account_scope": self.definition.account_scope,
            "container_scope": self.definition.container_scope,
            "capability": self.definition.capability,
            "state": self.state.value,
            "supported": self.supported,
            "reasons": list(self.reasons),
            "evidence": {
                "authenticated": self.evidence.authenticated,
                "account_context_valid": self.evidence.account_context_valid,
                "ui_attested": self.evidence.ui_attested,
                "runtime_healthy": self.evidence.runtime_healthy,
                "policy_allowed": self.evidence.policy_allowed,
                "license_available": self.evidence.license_available,
                "live_evidence": self.evidence.live_evidence,
            },
        }


def _evaluate(
    definition: ScopedCapability,
    evidence: EffectiveCapabilityEvidence,
) -> EffectiveCapability:
    if not evidence.policy_allowed:
        return EffectiveCapability(
            definition,
            EffectiveCapabilityState.BLOCKED,
            ("POLICY_DENIED",),
            evidence,
        )
    if not evidence.runtime_healthy:
        return EffectiveCapability(
            definition,
            EffectiveCapabilityState.BLOCKED,
            ("RUNTIME_UNHEALTHY",),
            evidence,
        )

    missing: list[str] = []
    if not evidence.authenticated:
        missing.append("AUTH_NOT_ATTESTED")
    if not evidence.account_context_valid:
        missing.append("ACCOUNT_CONTEXT_UNVERIFIED")
    if not evidence.ui_attested:
        missing.append("UI_NOT_ATTESTED")
    if not evidence.license_available:
        missing.append("LICENSE_UNVERIFIED")
    if not evidence.live_evidence:
        missing.append("LIVE_EVIDENCE_ABSENT")

    if missing:
        return EffectiveCapability(
            definition,
            EffectiveCapabilityState.UNVERIFIED_LIVE,
            tuple(missing),
            evidence,
        )

    return EffectiveCapability(
        definition,
        EffectiveCapabilityState.READ_SUPPORTED,
        ("ALL_REQUIRED_EVIDENCE_PRESENT",),
        evidence,
    )


def project_effective_capabilities(
    registry: CapabilityRegistry,
    *,
    application: str,
    evidence: EffectiveCapabilityEvidence,
) -> tuple[EffectiveCapability, ...]:
    """Compute deterministic effective state for every scoped app capability."""
    definitions = registry.by_application(application)
    return tuple(_evaluate(definition, evidence) for definition in definitions)
