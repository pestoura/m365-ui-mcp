"""Typed tenant-neutral Outlook mail-automation models for Phase 10.

The vocabulary is deliberately bounded. It describes synthetic rule state only and
never exposes selectors, browser primitives, tenant identities or executable mail
automation. Live UI support remains evidence-gated.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

_MAX_RULES = 200
_MAX_CLAUSES = 25


def _semantic_token(value: str, name: str) -> str:
    if not value or value != value.strip() or any(char.isspace() for char in value):
        raise ValueError(f"{name} must be a non-empty semantic token")
    return value


class RuleConditionKind(StrEnum):
    FROM_KEY = "FROM_KEY"
    TO_KEY = "TO_KEY"
    SUBJECT_CONTAINS_TEXT = "SUBJECT_CONTAINS_TEXT"
    BODY_CONTAINS_TEXT = "BODY_CONTAINS_TEXT"
    HAS_ATTACHMENT = "HAS_ATTACHMENT"
    IMPORTANCE = "IMPORTANCE"


class RuleActionKind(StrEnum):
    MOVE_TO_FOLDER = "MOVE_TO_FOLDER"
    COPY_TO_FOLDER = "COPY_TO_FOLDER"
    APPLY_CATEGORY = "APPLY_CATEGORY"
    MARK_READ = "MARK_READ"
    DELETE = "DELETE"

    @property
    def destructive(self) -> bool:
        return self is RuleActionKind.DELETE


@dataclass(frozen=True)
class RulePredicate:
    kind: RuleConditionKind
    value_key: str | None = None

    def __post_init__(self) -> None:
        value_required = self.kind is not RuleConditionKind.HAS_ATTACHMENT
        if value_required and self.value_key is None:
            raise ValueError(f"{self.kind.value} requires value_key")
        if not value_required and self.value_key is not None:
            raise ValueError("HAS_ATTACHMENT does not accept value_key")
        if self.value_key is not None:
            _semantic_token(self.value_key, "value_key")

    def to_projection(self) -> dict[str, object]:
        return {"kind": self.kind.value, "value_key": self.value_key}


@dataclass(frozen=True)
class RuleAction:
    kind: RuleActionKind
    target_key: str | None = None

    def __post_init__(self) -> None:
        target_required = self.kind in {
            RuleActionKind.MOVE_TO_FOLDER,
            RuleActionKind.COPY_TO_FOLDER,
            RuleActionKind.APPLY_CATEGORY,
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
        }


@dataclass(frozen=True)
class SyntheticMailRule:
    rule_key: str
    display_name: str
    order: int
    conditions: tuple[RulePredicate, ...]
    actions: tuple[RuleAction, ...]
    exceptions: tuple[RulePredicate, ...] = ()
    enabled: bool = True
    stop_processing: bool = False
    synthetic: bool = True

    def __post_init__(self) -> None:
        _semantic_token(self.rule_key, "rule_key")
        if not self.display_name or self.display_name != self.display_name.strip():
            raise ValueError("display_name must be non-empty and trimmed")
        if self.order < 1 or self.order > _MAX_RULES:
            raise ValueError("order is outside the bounded rule range")
        if not self.conditions:
            raise ValueError("mail rule requires at least one condition")
        if not self.actions:
            raise ValueError("mail rule requires at least one action")
        if len(self.conditions) > _MAX_CLAUSES or len(self.actions) > _MAX_CLAUSES:
            raise ValueError("mail rule exceeds bounded condition/action count")
        if len(self.exceptions) > _MAX_CLAUSES:
            raise ValueError("mail rule exceeds bounded exception count")
        if not self.synthetic:
            raise ValueError("mail automation foundation is synthetic-only")

    @property
    def destructive(self) -> bool:
        return any(action.kind.destructive for action in self.actions)

    def to_projection(self) -> dict[str, object]:
        return {
            "rule_key": self.rule_key,
            "display_name": self.display_name,
            "order": self.order,
            "enabled": self.enabled,
            "stop_processing": self.stop_processing,
            "conditions": [item.to_projection() for item in self.conditions],
            "actions": [item.to_projection() for item in self.actions],
            "exceptions": [item.to_projection() for item in self.exceptions],
            "destructive": self.destructive,
            "synthetic": True,
        }


def validate_rule_catalog(rules: tuple[SyntheticMailRule, ...]) -> None:
    if len(rules) > _MAX_RULES:
        raise ValueError("rule catalog exceeds bounded size")
    keys = tuple(rule.rule_key for rule in rules)
    if len(keys) != len(set(keys)):
        raise ValueError("rule keys must be unique")
    orders = tuple(rule.order for rule in rules)
    if len(orders) != len(set(orders)):
        raise ValueError("rule order values must be unique")
    if orders and set(orders) != set(range(1, len(orders) + 1)):
        raise ValueError("rule order must be contiguous starting at 1")
    if any(not rule.synthetic for rule in rules):
        raise ValueError("rule catalog must remain synthetic")


def default_synthetic_rules() -> tuple[SyntheticMailRule, ...]:
    rules = (
        SyntheticMailRule(
            rule_key="rule-project",
            display_name="Synthetic project routing",
            order=1,
            conditions=(RulePredicate(RuleConditionKind.FROM_KEY, "person-alpha"),),
            actions=(RuleAction(RuleActionKind.MOVE_TO_FOLDER, "archive"),),
            stop_processing=True,
        ),
        SyntheticMailRule(
            rule_key="rule-followup",
            display_name="Synthetic follow-up categorization",
            order=2,
            conditions=(
                RulePredicate(RuleConditionKind.SUBJECT_CONTAINS_TEXT, "followup"),
            ),
            actions=(RuleAction(RuleActionKind.APPLY_CATEGORY, "cat-followup"),),
        ),
    )
    validate_rule_catalog(rules)
    return rules


__all__ = [
    "RuleAction",
    "RuleActionKind",
    "RuleConditionKind",
    "RulePredicate",
    "SyntheticMailRule",
    "default_synthetic_rules",
    "validate_rule_catalog",
]
