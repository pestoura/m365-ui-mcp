"""Typed tenant-neutral Quick Step models for Outlook Phase 10.

The foundation is synthetic-only. It models bounded Quick Step definitions and
classification metadata without selectors, browser primitives, tenant identities,
mailbox addresses or executable UI operations. OUT-067 owns execution policy.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

_MAX_QUICK_STEPS = 50
_MAX_ACTIONS = 10


def _semantic_token(value: str, name: str) -> str:
    if not value or value != value.strip() or any(char.isspace() for char in value):
        raise ValueError(f"{name} must be a non-empty semantic token")
    return value


class QuickStepActionKind(StrEnum):
    """Closed semantic vocabulary; none of these values drives a browser."""

    MOVE_TO_FOLDER = "MOVE_TO_FOLDER"
    APPLY_CATEGORY = "APPLY_CATEGORY"
    MARK_READ = "MARK_READ"
    FLAG = "FLAG"
    DELETE = "DELETE"
    REPLY_WITH_TEMPLATE = "REPLY_WITH_TEMPLATE"
    FORWARD_TO_RECIPIENT = "FORWARD_TO_RECIPIENT"

    @property
    def destructive(self) -> bool:
        return self is QuickStepActionKind.DELETE

    @property
    def outbound(self) -> bool:
        return self in {
            QuickStepActionKind.REPLY_WITH_TEMPLATE,
            QuickStepActionKind.FORWARD_TO_RECIPIENT,
        }


class QuickStepShortcut(StrEnum):
    NONE = "NONE"
    CTRL_SHIFT_1 = "CTRL_SHIFT_1"
    CTRL_SHIFT_2 = "CTRL_SHIFT_2"
    CTRL_SHIFT_3 = "CTRL_SHIFT_3"
    CTRL_SHIFT_4 = "CTRL_SHIFT_4"
    CTRL_SHIFT_5 = "CTRL_SHIFT_5"
    CTRL_SHIFT_6 = "CTRL_SHIFT_6"
    CTRL_SHIFT_7 = "CTRL_SHIFT_7"
    CTRL_SHIFT_8 = "CTRL_SHIFT_8"
    CTRL_SHIFT_9 = "CTRL_SHIFT_9"


@dataclass(frozen=True)
class QuickStepAction:
    kind: QuickStepActionKind
    target_key: str | None = None

    def __post_init__(self) -> None:
        target_required = self.kind in {
            QuickStepActionKind.MOVE_TO_FOLDER,
            QuickStepActionKind.APPLY_CATEGORY,
            QuickStepActionKind.REPLY_WITH_TEMPLATE,
            QuickStepActionKind.FORWARD_TO_RECIPIENT,
        }
        if target_required and self.target_key is None:
            raise ValueError(f"{self.kind.value} requires target_key")
        if not target_required and self.target_key is not None:
            raise ValueError(f"{self.kind.value} does not accept target_key")
        if self.target_key is not None:
            _semantic_token(self.target_key, "target_key")

    def to_projection(self) -> dict[str, object]:
        return {
            "kind": self.kind.value,
            "target_key": self.target_key,
            "destructive": self.kind.destructive,
            "outbound": self.kind.outbound,
        }


@dataclass(frozen=True)
class SyntheticQuickStep:
    quick_step_key: str
    display_name: str
    order: int
    actions: tuple[QuickStepAction, ...]
    description: str | None = None
    shortcut: QuickStepShortcut = QuickStepShortcut.NONE
    synthetic: bool = True

    def __post_init__(self) -> None:
        _semantic_token(self.quick_step_key, "quick_step_key")
        if not self.display_name or self.display_name != self.display_name.strip():
            raise ValueError("display_name must be non-empty and trimmed")
        if self.description is not None:
            if not self.description or self.description != self.description.strip():
                raise ValueError("description must be non-empty and trimmed when set")
            if len(self.description) > 240:
                raise ValueError("description exceeds bounded length")
        if self.order < 1 or self.order > _MAX_QUICK_STEPS:
            raise ValueError("order is outside the bounded Quick Step range")
        if not self.actions or len(self.actions) > _MAX_ACTIONS:
            raise ValueError("Quick Step requires a bounded non-empty action list")
        if not isinstance(self.shortcut, QuickStepShortcut):
            raise ValueError("shortcut must be a closed QuickStepShortcut")
        if not self.synthetic:
            raise ValueError("Quick Step foundation is synthetic-only")

    @property
    def destructive(self) -> bool:
        return any(action.kind.destructive for action in self.actions)

    @property
    def outbound(self) -> bool:
        return any(action.kind.outbound for action in self.actions)

    def to_projection(self) -> dict[str, object]:
        return {
            "quick_step_key": self.quick_step_key,
            "display_name": self.display_name,
            "description": self.description,
            "order": self.order,
            "shortcut": self.shortcut.value,
            "actions": [action.to_projection() for action in self.actions],
            "destructive": self.destructive,
            "outbound": self.outbound,
            "synthetic": True,
        }


def validate_quick_step_catalog(steps: tuple[SyntheticQuickStep, ...]) -> None:
    if len(steps) > _MAX_QUICK_STEPS:
        raise ValueError("Quick Step catalog exceeds bounded size")
    keys = tuple(step.quick_step_key for step in steps)
    if len(keys) != len(set(keys)):
        raise ValueError("Quick Step keys must be unique")
    orders = tuple(step.order for step in steps)
    if len(orders) != len(set(orders)):
        raise ValueError("Quick Step order values must be unique")
    if orders and set(orders) != set(range(1, len(orders) + 1)):
        raise ValueError("Quick Step order must be contiguous starting at 1")
    shortcuts = tuple(
        step.shortcut for step in steps if step.shortcut is not QuickStepShortcut.NONE
    )
    if len(shortcuts) != len(set(shortcuts)):
        raise ValueError("non-NONE Quick Step shortcuts must be unique")
    if any(not step.synthetic for step in steps):
        raise ValueError("Quick Step catalog must remain synthetic")


def default_synthetic_quick_steps() -> tuple[SyntheticQuickStep, ...]:
    steps = (
        SyntheticQuickStep(
            quick_step_key="quick-archive-read",
            display_name="Synthetic archive and read",
            description="Synthetic safe mail triage",
            order=1,
            shortcut=QuickStepShortcut.CTRL_SHIFT_1,
            actions=(
                QuickStepAction(QuickStepActionKind.MOVE_TO_FOLDER, "archive"),
                QuickStepAction(QuickStepActionKind.MARK_READ),
            ),
        ),
        SyntheticQuickStep(
            quick_step_key="quick-followup",
            display_name="Synthetic follow up",
            description="Synthetic follow-up classification",
            order=2,
            shortcut=QuickStepShortcut.CTRL_SHIFT_2,
            actions=(
                QuickStepAction(QuickStepActionKind.APPLY_CATEGORY, "cat-followup"),
                QuickStepAction(QuickStepActionKind.FLAG),
            ),
        ),
    )
    validate_quick_step_catalog(steps)
    return steps


__all__ = [
    "QuickStepAction",
    "QuickStepActionKind",
    "QuickStepShortcut",
    "SyntheticQuickStep",
    "default_synthetic_quick_steps",
    "validate_quick_step_catalog",
]
