"""Planner-owned UIContract fragment declarations for PLN-MIG-004.

The declarations identify the Planner-specific portion of the canonical
fragmented UIContract. Common authentication fragments remain platform-owned.
No selector values are duplicated here; canonical selector metadata continues
to live in the validated contract documents under ``contracts/ui_fragments``.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PlannerUIContractFragmentSpec:
    """Stable application-owned identity and dependency shape for one fragment."""

    fragment_id: str
    scope: str
    surface: str | None
    capability_keys: tuple[str, ...]
    selector_names: tuple[str, ...]


def planner_ui_contract_fragment_specs() -> tuple[PlannerUIContractFragmentSpec, ...]:
    """Return the canonical Planner fragment partition in manifest order."""
    return (
        PlannerUIContractFragmentSpec(
            fragment_id="planner.plan-surface",
            scope="surface",
            surface="planner-premium-web",
            capability_keys=("plans.read", "project_snapshot.read"),
            selector_names=("plan.list_container", "plan.list_item", "plan.title"),
        ),
        PlannerUIContractFragmentSpec(
            fragment_id="planner.task-surface",
            scope="surface",
            surface="planner-premium-web",
            capability_keys=("tasks.read", "buckets.read", "project_snapshot.read"),
            selector_names=(
                "task.list_container",
                "task.list_item",
                "task.title",
                "task.bucket",
            ),
        ),
        PlannerUIContractFragmentSpec(
            fragment_id="planner.account",
            scope="application",
            surface=None,
            capability_keys=(),
            selector_names=("account.context_menu",),
        ),
    )


def planner_selector_names() -> tuple[str, ...]:
    """Return the eight Planner-owned historical selector names deterministically."""
    return tuple(
        selector
        for fragment in planner_ui_contract_fragment_specs()
        for selector in fragment.selector_names
    )


__all__ = [
    "PlannerUIContractFragmentSpec",
    "planner_selector_names",
    "planner_ui_contract_fragment_specs",
]
