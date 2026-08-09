"""Synthetic-only bounded Quick Step list/get reads for OUT-065."""

from __future__ import annotations

from dataclasses import dataclass

from m365_mcp.apps.outlook.quick_step_models import (
    SyntheticQuickStep,
    default_synthetic_quick_steps,
    validate_quick_step_catalog,
)
from m365_mcp.apps.outlook.readiness import OutlookReadinessReport


@dataclass(frozen=True)
class QuickStepListResult:
    steps: tuple[SyntheticQuickStep, ...]
    quick_step_count: int
    destructive_count: int
    outbound_count: int
    synthetic: bool


@dataclass(frozen=True)
class QuickStepGetResult:
    step: SyntheticQuickStep
    synthetic: bool


def list_quick_steps(
    *,
    readiness: OutlookReadinessReport,
    steps: tuple[SyntheticQuickStep, ...] | None = None,
) -> QuickStepListResult:
    """List the bounded synthetic Quick Step catalog in deterministic order."""
    if not readiness.ready_for_readonly_discovery:
        raise ValueError("Outlook read-only discovery is not ready")
    catalog = default_synthetic_quick_steps() if steps is None else steps
    validate_quick_step_catalog(catalog)
    ordered = tuple(sorted(catalog, key=lambda item: item.order))
    return QuickStepListResult(
        steps=ordered,
        quick_step_count=len(ordered),
        destructive_count=sum(1 for item in ordered if item.destructive),
        outbound_count=sum(1 for item in ordered if item.outbound),
        synthetic=True,
    )


def get_quick_step(
    quick_step_key: str,
    *,
    readiness: OutlookReadinessReport,
    steps: tuple[SyntheticQuickStep, ...] | None = None,
) -> QuickStepGetResult:
    """Get exactly one synthetic Quick Step by semantic key."""
    if not quick_step_key or quick_step_key != quick_step_key.strip():
        raise ValueError("quick_step_key must be non-empty and trimmed")
    listing = list_quick_steps(readiness=readiness, steps=steps)
    matches = tuple(
        item for item in listing.steps if item.quick_step_key == quick_step_key
    )
    if len(matches) != 1:
        raise ValueError("Quick Step key must resolve to exactly one synthetic item")
    return QuickStepGetResult(step=matches[0], synthetic=True)


__all__ = [
    "QuickStepGetResult",
    "QuickStepListResult",
    "get_quick_step",
    "list_quick_steps",
]
