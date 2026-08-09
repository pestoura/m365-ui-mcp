"""Sanitized Outlook readiness/smoke model for OUT-007.

The model composes the inert Outlook foundation, discovery evidence and mailbox
context verification without promoting live support. It deliberately carries no
mailbox/account/tenant identity, selector, URL or session material.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from m365_mcp.apps.outlook.discovery import DiscoveryState, OutlookCapabilityCandidate
from m365_mcp.apps.outlook.mailbox_context import (
    PrimaryMailboxContext,
    PrimaryMailboxContextState,
)
from m365_mcp.apps.outlook.manifest import foundation_manifest
from m365_mcp.apps.outlook.shared_mailbox_context import (
    SharedMailboxContext,
    SharedMailboxContextState,
)


class OutlookReadinessState(StrEnum):
    """Closed readiness states that never imply public/live support."""

    FOUNDATION_READY = "FOUNDATION_READY"
    DISCOVERY_READY = "DISCOVERY_READY"
    BLOCKED = "BLOCKED"
    REATTESTATION_REQUIRED = "REATTESTATION_REQUIRED"


@dataclass(frozen=True)
class OutlookReadinessReport:
    """Low-cardinality readiness projection safe for health/smoke use."""

    state: OutlookReadinessState
    primary_context_verified: bool
    shared_context_verified: bool
    candidate_count: int
    observed_count: int
    blocked_count: int
    reattestation_count: int

    @property
    def ready_for_readonly_discovery(self) -> bool:
        """Return whether evidence-backed read-only discovery may proceed."""
        return (
            self.state is OutlookReadinessState.DISCOVERY_READY
            and self.primary_context_verified
            and self.observed_count > 0
            and self.blocked_count == 0
            and self.reattestation_count == 0
        )

    def to_dict(self) -> dict[str, object]:
        """Project bounded readiness state without identity-bearing values."""
        return {
            "state": self.state.value,
            "primary_context_verified": self.primary_context_verified,
            "shared_context_verified": self.shared_context_verified,
            "candidate_count": self.candidate_count,
            "observed_count": self.observed_count,
            "blocked_count": self.blocked_count,
            "reattestation_count": self.reattestation_count,
            "ready_for_readonly_discovery": self.ready_for_readonly_discovery,
            "live_support_promoted": False,
            "public_tools_enabled": False,
            "browser_operations_enabled": False,
        }


def evaluate_outlook_readiness(
    primary_context: PrimaryMailboxContext,
    candidates: tuple[OutlookCapabilityCandidate, ...],
    *,
    shared_context: SharedMailboxContext | None = None,
) -> OutlookReadinessReport:
    """Evaluate Outlook foundation/read-discovery readiness fail closed."""
    manifest = foundation_manifest()
    if manifest.public_tools_enabled or manifest.browser_operations_enabled:
        raise ValueError("OUT-007 requires inert Outlook execution surfaces")

    if not candidates:
        raise ValueError("Outlook readiness requires discovery candidates")
    capability_keys = tuple(candidate.capability_key for candidate in candidates)
    if len(set(capability_keys)) != len(capability_keys):
        raise ValueError("Outlook readiness candidates must be unique")

    observed_count = sum(candidate.state is DiscoveryState.OBSERVED for candidate in candidates)
    blocked_count = sum(candidate.state is DiscoveryState.BLOCKED for candidate in candidates)
    reattestation_count = sum(
        candidate.state is DiscoveryState.REATTESTATION_REQUIRED for candidate in candidates
    )

    primary_reattestation = (
        primary_context.state is PrimaryMailboxContextState.REATTESTATION_REQUIRED
    )
    shared_reattestation = (
        shared_context is not None
        and shared_context.state is SharedMailboxContextState.REATTESTATION_REQUIRED
    )
    if primary_reattestation or shared_reattestation or reattestation_count:
        state = OutlookReadinessState.REATTESTATION_REQUIRED
    elif not primary_context.valid or blocked_count:
        state = OutlookReadinessState.BLOCKED
    elif observed_count:
        state = OutlookReadinessState.DISCOVERY_READY
    else:
        state = OutlookReadinessState.FOUNDATION_READY

    return OutlookReadinessReport(
        state=state,
        primary_context_verified=primary_context.valid,
        shared_context_verified=shared_context.valid if shared_context is not None else False,
        candidate_count=len(candidates),
        observed_count=observed_count,
        blocked_count=blocked_count,
        reattestation_count=reattestation_count,
    )


__all__ = [
    "OutlookReadinessReport",
    "OutlookReadinessState",
    "evaluate_outlook_readiness",
]
