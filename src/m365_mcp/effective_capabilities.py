"""Effective capability projection from scoped definitions plus runtime evidence."""

from __future__ import annotations

from collections.abc import Mapping
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
    ui_drifted: bool = False
    ui_stale: bool = False
    ui_reattestation_required: bool = False
    # Read-only delivery capabilities (plans.read / tasks.read /
    # project_snapshot.read) are authorized by the verified professional session
    # on the live Planner Web surface, NOT by UIContract fragment attestation or
    # license metadata. This dimension is True only when the broker has actually
    # authorized the read path at runtime.
    live_read_path: bool = False


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
                "ui_drifted": self.evidence.ui_drifted,
                "ui_stale": self.evidence.ui_stale,
                "ui_reattestation_required": self.evidence.ui_reattestation_required,
                "live_read_path": self.evidence.live_read_path,
            },
        }


_READ_ONLY_UI_CAPABILITIES = frozenset(
    {"plans.read", "tasks.read", "project_snapshot.read"}
)


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

    # Read-only delivery capabilities are authorized by the verified professional
    # session on the live Planner Web surface (broker Gate-1), independent of
    # UIContract fragment attestation and tenant license metadata. This is the
    # deliberate first-delivery gate: the read path performs real Playwright
    # extraction against the authenticated board, and no UI attestation is
    # required to read already-rendered non-secret surface text. Mutation
    # capabilities and every other capability remain gated on UI attestation
    # below, so this does NOT widen the write surface.
    if definition.capability in _READ_ONLY_UI_CAPABILITIES:
        # The read is authorized by the verified professional session on the live
        # Planner Web surface (broker Gate-1), independent of UIContract fragment
        # attestation and tenant license metadata. The absence of the auth/account/
        # live-read path is a hard block (UNVERIFIED_LIVE); it is NOT merely a
        # degradation, because without the verified live read path there is nothing
        # to read.
        read_missing: list[str] = []
        if not evidence.authenticated:
            read_missing.append("AUTH_NOT_ATTESTED")
        if not evidence.account_context_valid:
            read_missing.append("ACCOUNT_CONTEXT_UNVERIFIED")
        if not evidence.live_evidence:
            read_missing.append("LIVE_EVIDENCE_ABSENT")
        if not evidence.live_read_path:
            read_missing.append("LIVE_READ_PATH_UNAVAILABLE")
        if read_missing:
            return EffectiveCapability(
                definition,
                EffectiveCapabilityState.UNVERIFIED_LIVE,
                tuple(read_missing),
                evidence,
            )
        # The live read path is verified, so the read is supported. However, when a
        # Planner Web fragment the read depends on has drifted or is stale, the
        # rendered surface may no longer match the expected layout, so the read is
        # downgraded to DEGRADED rather than silently trusted. This preserves the
        # fail-closed UI-lifecycle discipline for the read path.
        read_lifecycle_reason: str | None = None
        if evidence.ui_drifted:
            read_lifecycle_reason = "UI_FRAGMENT_DRIFT"
        elif evidence.ui_stale:
            read_lifecycle_reason = "UI_EVIDENCE_STALE"
        elif evidence.ui_reattestation_required:
            read_lifecycle_reason = "UI_RE_ATTESTATION_REQUIRED"
        if read_lifecycle_reason is not None:
            return EffectiveCapability(
                definition,
                EffectiveCapabilityState.DEGRADED,
                (read_lifecycle_reason,),
                evidence,
            )
        return EffectiveCapability(
            definition,
            EffectiveCapabilityState.READ_SUPPORTED,
            ("LIVE_READ_PATH_VERIFIED",),
            evidence,
        )

    missing: list[str] = []
    if not evidence.authenticated:
        missing.append("AUTH_NOT_ATTESTED")
    if not evidence.account_context_valid:
        missing.append("ACCOUNT_CONTEXT_UNVERIFIED")
    if not evidence.license_available:
        missing.append("LICENSE_UNVERIFIED")
    if not evidence.live_evidence:
        missing.append("LIVE_EVIDENCE_ABSENT")

    lifecycle_reason: str | None = None
    if evidence.ui_drifted:
        lifecycle_reason = "UI_FRAGMENT_DRIFT"
    elif evidence.ui_reattestation_required:
        lifecycle_reason = "UI_RE_ATTESTATION_REQUIRED"
    elif evidence.ui_stale:
        lifecycle_reason = "UI_EVIDENCE_STALE"

    if lifecycle_reason is not None:
        if missing:
            return EffectiveCapability(
                definition,
                EffectiveCapabilityState.UNVERIFIED_LIVE,
                tuple((*missing, lifecycle_reason)),
                evidence,
            )
        return EffectiveCapability(
            definition,
            EffectiveCapabilityState.DEGRADED,
            (lifecycle_reason,),
            evidence,
        )

    if not evidence.ui_attested:
        missing.append("UI_NOT_ATTESTED")
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
    """Compute one shared evidence state for every scoped app capability."""
    definitions = registry.by_application(application)
    return tuple(_evaluate(definition, evidence) for definition in definitions)


def project_effective_capabilities_by_capability(
    registry: CapabilityRegistry,
    *,
    application: str,
    evidence_by_capability: Mapping[str, EffectiveCapabilityEvidence],
) -> tuple[EffectiveCapability, ...]:
    """Compute capability-specific states and reject incomplete evidence maps."""
    definitions = registry.by_application(application)
    expected = {definition.capability for definition in definitions}
    supplied = set(evidence_by_capability)
    if expected != supplied:
        raise ValueError("capability-specific evidence must cover the exact registry surface")
    return tuple(
        _evaluate(definition, evidence_by_capability[definition.capability])
        for definition in definitions
    )
