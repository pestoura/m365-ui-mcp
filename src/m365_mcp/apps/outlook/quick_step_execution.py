"""Governed synthetic Quick Step execution policy for OUT-067.

Safe actions may transform a synthetic message state. Outbound Quick Steps are
prepare-only and never partially apply accompanying safe actions. Destructive
actions require explicit policy allowance. No browser/UI operation is performed.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from m365_mcp.apps.outlook.quick_step_models import (
    QuickStepActionKind,
    SyntheticQuickStep,
    default_synthetic_quick_steps,
    validate_quick_step_catalog,
)
from m365_mcp.apps.outlook.readiness import OutlookReadinessReport


class QuickStepExecutionDisposition(StrEnum):
    APPLIED_SYNTHETIC = "APPLIED_SYNTHETIC"
    PREPARED_OUTBOUND = "PREPARED_OUTBOUND"


@dataclass(frozen=True)
class QuickStepMessageState:
    message_key: str
    folder_key: str
    category_keys: tuple[str, ...] = ()
    is_read: bool = False
    flagged: bool = False
    deleted: bool = False
    synthetic: bool = True

    def __post_init__(self) -> None:
        for field_name in ("message_key", "folder_key"):
            value = getattr(self, field_name)
            invalid = (
                not value
                or value != value.strip()
                or any(char.isspace() for char in value)
            )
            if invalid:
                raise ValueError(f"{field_name} must be a non-empty semantic token")
        if len(set(self.category_keys)) != len(self.category_keys):
            raise ValueError("category_keys must be unique")
        for category_key in self.category_keys:
            if (
                not category_key
                or category_key != category_key.strip()
                or any(char.isspace() for char in category_key)
            ):
                raise ValueError("category_keys must contain semantic tokens")
        if not self.synthetic:
            raise ValueError("Quick Step execution state is synthetic-only")

    def to_projection(self) -> dict[str, object]:
        return {
            "message_key": self.message_key,
            "folder_key": self.folder_key,
            "category_keys": list(self.category_keys),
            "is_read": self.is_read,
            "flagged": self.flagged,
            "deleted": self.deleted,
            "synthetic": True,
        }


@dataclass(frozen=True)
class QuickStepExecutionRequest:
    quick_step_key: str
    message_key: str

    def __post_init__(self) -> None:
        for field_name in ("quick_step_key", "message_key"):
            value = getattr(self, field_name)
            invalid = (
                not value
                or value != value.strip()
                or any(char.isspace() for char in value)
            )
            if invalid:
                raise ValueError(f"{field_name} must be a non-empty semantic token")

    def to_payload(self) -> dict[str, object]:
        return {
            "quick_step_key": self.quick_step_key,
            "message_key": self.message_key,
        }


@dataclass(frozen=True)
class QuickStepExecutionResult:
    quick_step_key: str
    message_key: str
    disposition: QuickStepExecutionDisposition
    changed: bool
    verified: bool
    read_back: QuickStepMessageState
    prepared_action_kinds: tuple[str, ...]
    synthetic: bool = True


def _select_step(
    steps: tuple[SyntheticQuickStep, ...],
    quick_step_key: str,
) -> SyntheticQuickStep:
    matches = tuple(step for step in steps if step.quick_step_key == quick_step_key)
    if len(matches) != 1:
        raise ValueError("Quick Step key must resolve to exactly one synthetic item")
    return matches[0]


def execute_quick_step(
    state: QuickStepMessageState,
    request: QuickStepExecutionRequest,
    *,
    readiness: OutlookReadinessReport,
    steps: tuple[SyntheticQuickStep, ...] | None = None,
    allow_destructive: bool = False,
    allow_outbound_prepare: bool = False,
) -> tuple[QuickStepMessageState, QuickStepExecutionResult]:
    """Apply or prepare one Quick Step under fail-closed synthetic policy."""
    if not readiness.ready_for_readonly_discovery:
        raise ValueError("Outlook read-only discovery is not ready")
    if state.message_key != request.message_key:
        raise ValueError("request message_key must match synthetic state")

    catalog = default_synthetic_quick_steps() if steps is None else steps
    validate_quick_step_catalog(catalog)
    step = _select_step(catalog, request.quick_step_key)

    if step.destructive and not allow_destructive:
        raise PermissionError("destructive Quick Step execution requires explicit policy allowance")
    if step.outbound:
        if not allow_outbound_prepare:
            raise PermissionError("outbound Quick Step requires explicit prepare-only allowance")
        prepared = tuple(
            action.kind.value for action in step.actions if action.kind.outbound
        )
        return state, QuickStepExecutionResult(
            quick_step_key=step.quick_step_key,
            message_key=state.message_key,
            disposition=QuickStepExecutionDisposition.PREPARED_OUTBOUND,
            changed=False,
            verified=True,
            read_back=state,
            prepared_action_kinds=prepared,
        )

    folder_key = state.folder_key
    categories = list(state.category_keys)
    is_read = state.is_read
    flagged = state.flagged
    deleted = state.deleted

    for action in step.actions:
        if action.kind is QuickStepActionKind.MOVE_TO_FOLDER:
            assert action.target_key is not None
            folder_key = action.target_key
        elif action.kind is QuickStepActionKind.APPLY_CATEGORY:
            assert action.target_key is not None
            if action.target_key not in categories:
                categories.append(action.target_key)
                categories.sort()
        elif action.kind is QuickStepActionKind.MARK_READ:
            is_read = True
        elif action.kind is QuickStepActionKind.FLAG:
            flagged = True
        elif action.kind is QuickStepActionKind.DELETE:
            deleted = True
        else:
            raise RuntimeError("outbound Quick Step action escaped prepare-only policy")

    updated = QuickStepMessageState(
        message_key=state.message_key,
        folder_key=folder_key,
        category_keys=tuple(categories),
        is_read=is_read,
        flagged=flagged,
        deleted=deleted,
    )
    return updated, QuickStepExecutionResult(
        quick_step_key=step.quick_step_key,
        message_key=state.message_key,
        disposition=QuickStepExecutionDisposition.APPLIED_SYNTHETIC,
        changed=updated != state,
        verified=True,
        read_back=updated,
        prepared_action_kinds=(),
    )


__all__ = [
    "QuickStepExecutionDisposition",
    "QuickStepExecutionRequest",
    "QuickStepExecutionResult",
    "QuickStepMessageState",
    "execute_quick_step",
]
