"""Synthetic Outlook Quick Step create/update/delete semantics for OUT-066."""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import StrEnum

from m365_mcp.apps.outlook.quick_step_models import (
    SyntheticQuickStep,
    validate_quick_step_catalog,
)
from m365_mcp.apps.outlook.readiness import OutlookReadinessReport


class QuickStepMutationAction(StrEnum):
    CREATE = "CREATE"
    UPDATE = "UPDATE"
    DELETE = "DELETE"


@dataclass(frozen=True)
class QuickStepMutationRequest:
    action: QuickStepMutationAction
    quick_step_key: str
    step: SyntheticQuickStep | None = None

    def __post_init__(self) -> None:
        invalid = (
            not self.quick_step_key
            or self.quick_step_key != self.quick_step_key.strip()
            or any(char.isspace() for char in self.quick_step_key)
        )
        if invalid:
            raise ValueError("quick_step_key must be a non-empty semantic token")
        if self.action in {
            QuickStepMutationAction.CREATE,
            QuickStepMutationAction.UPDATE,
        }:
            if self.step is None or self.step.quick_step_key != self.quick_step_key:
                raise ValueError("CREATE/UPDATE requires a matching synthetic Quick Step")
        elif self.step is not None:
            raise ValueError("DELETE does not accept step")

    def to_payload(self) -> dict[str, object]:
        return {
            "action": self.action.value,
            "quick_step_key": self.quick_step_key,
            "step": None if self.step is None else self.step.to_projection(),
        }


@dataclass(frozen=True)
class QuickStepMutationResult:
    quick_step_key: str
    action: QuickStepMutationAction
    changed: bool
    verified: bool
    read_back: SyntheticQuickStep | None
    synthetic: bool = True


def _read_back(
    steps: tuple[SyntheticQuickStep, ...],
    quick_step_key: str,
) -> SyntheticQuickStep | None:
    matches = tuple(step for step in steps if step.quick_step_key == quick_step_key)
    if len(matches) > 1:
        raise RuntimeError("synthetic Quick Step read-back became ambiguous")
    return matches[0] if matches else None


def _ordered(
    steps: tuple[SyntheticQuickStep, ...],
) -> tuple[SyntheticQuickStep, ...]:
    return tuple(
        replace(step, order=index)
        for index, step in enumerate(sorted(steps, key=lambda item: item.order), 1)
    )


def _apply_update(
    steps: tuple[SyntheticQuickStep, ...],
    replacement: SyntheticQuickStep,
) -> tuple[SyntheticQuickStep, ...]:
    without = [
        step for step in sorted(steps, key=lambda item: item.order)
        if step.quick_step_key != replacement.quick_step_key
    ]
    target_index = replacement.order - 1
    if target_index < 0 or target_index > len(without):
        raise ValueError("UPDATE target order is outside the current Quick Step catalog")
    without.insert(target_index, replacement)
    return tuple(replace(step, order=index) for index, step in enumerate(without, 1))


def mutate_quick_steps(
    steps: tuple[SyntheticQuickStep, ...],
    request: QuickStepMutationRequest,
    *,
    readiness: OutlookReadinessReport,
    allow_sensitive_definition: bool = False,
) -> tuple[tuple[SyntheticQuickStep, ...], QuickStepMutationResult]:
    """Apply one synthetic Quick Step lifecycle change with deterministic read-back."""
    if not readiness.ready_for_readonly_discovery:
        raise ValueError("Outlook read-only discovery is not ready")
    validate_quick_step_catalog(steps)
    current = _read_back(steps, request.quick_step_key)

    if request.action is QuickStepMutationAction.CREATE:
        assert request.step is not None
        if current is not None:
            raise ValueError("CREATE requires a new quick_step_key")
        if request.step.order != len(steps) + 1:
            raise ValueError("CREATE order must append to the Quick Step catalog")
        if (request.step.destructive or request.step.outbound) and not allow_sensitive_definition:
            raise PermissionError("sensitive Quick Step definition requires explicit policy allowance")
        updated = steps + (request.step,)
        changed = True
    elif request.action is QuickStepMutationAction.UPDATE:
        assert request.step is not None
        if current is None:
            raise ValueError("UPDATE requires an existing quick_step_key")
        if (request.step.destructive or request.step.outbound) and not allow_sensitive_definition:
            raise PermissionError("sensitive Quick Step definition requires explicit policy allowance")
        updated = _apply_update(steps, request.step)
        changed = request.step != current
    else:
        if current is None:
            updated = steps
            changed = False
        else:
            updated = _ordered(
                tuple(
                    step for step in steps if step.quick_step_key != request.quick_step_key
                )
            )
            changed = True

    validate_quick_step_catalog(updated)
    read_back = _read_back(updated, request.quick_step_key)
    if request.action in {
        QuickStepMutationAction.CREATE,
        QuickStepMutationAction.UPDATE,
    }:
        if read_back != request.step:
            raise RuntimeError("synthetic read-back did not prove Quick Step lifecycle state")
    elif read_back is not None:
        raise RuntimeError("synthetic read-back did not prove Quick Step deletion")

    return updated, QuickStepMutationResult(
        quick_step_key=request.quick_step_key,
        action=request.action,
        changed=changed,
        verified=True,
        read_back=read_back,
    )


__all__ = [
    "QuickStepMutationAction",
    "QuickStepMutationRequest",
    "QuickStepMutationResult",
    "mutate_quick_steps",
]
