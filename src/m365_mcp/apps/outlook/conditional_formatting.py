"""Synthetic conditional-formatting management for OUT-068.

Rules are display-only semantic metadata. No CSS, selector, DOM property or
message mutation is represented.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import StrEnum

from m365_mcp.apps.outlook.readiness import OutlookReadinessReport

_MAX_RULES = 50


def _semantic_token(value: str, name: str) -> str:
    if not value or value != value.strip() or any(char.isspace() for char in value):
        raise ValueError(f"{name} must be a non-empty semantic token")
    return value


class FormattingConditionKind(StrEnum):
    FROM_KEY = "FROM_KEY"
    SUBJECT_CONTAINS_TEXT = "SUBJECT_CONTAINS_TEXT"
    TO_OR_CC_KEY = "TO_OR_CC_KEY"
    IMPORTANCE = "IMPORTANCE"


class FormattingColorToken(StrEnum):
    DEFAULT = "DEFAULT"
    RED = "RED"
    ORANGE = "ORANGE"
    GREEN = "GREEN"
    BLUE = "BLUE"
    PURPLE = "PURPLE"


@dataclass(frozen=True)
class FormattingCondition:
    kind: FormattingConditionKind
    value_key: str

    def __post_init__(self) -> None:
        _semantic_token(self.value_key, "value_key")

    def to_projection(self) -> dict[str, object]:
        return {"kind": self.kind.value, "value_key": self.value_key}


@dataclass(frozen=True)
class FormattingStyle:
    color: FormattingColorToken = FormattingColorToken.DEFAULT
    bold: bool = False
    italic: bool = False

    def to_projection(self) -> dict[str, object]:
        return {
            "color": self.color.value,
            "bold": self.bold,
            "italic": self.italic,
        }


@dataclass(frozen=True)
class SyntheticFormattingRule:
    rule_key: str
    display_name: str
    order: int
    condition: FormattingCondition
    style: FormattingStyle
    enabled: bool = True
    synthetic: bool = True

    def __post_init__(self) -> None:
        _semantic_token(self.rule_key, "rule_key")
        if not self.display_name or self.display_name != self.display_name.strip():
            raise ValueError("display_name must be non-empty and trimmed")
        if self.order < 1 or self.order > _MAX_RULES:
            raise ValueError("order is outside the bounded formatting-rule range")
        if not self.synthetic:
            raise ValueError("conditional formatting is synthetic-only")

    def to_projection(self) -> dict[str, object]:
        return {
            "rule_key": self.rule_key,
            "display_name": self.display_name,
            "order": self.order,
            "condition": self.condition.to_projection(),
            "style": self.style.to_projection(),
            "enabled": self.enabled,
            "synthetic": True,
        }


def validate_formatting_rules(rules: tuple[SyntheticFormattingRule, ...]) -> None:
    if len(rules) > _MAX_RULES:
        raise ValueError("conditional-formatting catalog exceeds bounded size")
    keys = tuple(rule.rule_key for rule in rules)
    if len(keys) != len(set(keys)):
        raise ValueError("conditional-formatting rule keys must be unique")
    orders = tuple(rule.order for rule in rules)
    if len(orders) != len(set(orders)):
        raise ValueError("conditional-formatting order values must be unique")
    if orders and set(orders) != set(range(1, len(orders) + 1)):
        raise ValueError("conditional-formatting order must be contiguous starting at 1")
    if any(not rule.synthetic for rule in rules):
        raise ValueError("conditional-formatting catalog must remain synthetic")


def default_synthetic_formatting_rules() -> tuple[SyntheticFormattingRule, ...]:
    rules = (
        SyntheticFormattingRule(
            rule_key="format-project",
            display_name="Synthetic project sender",
            order=1,
            condition=FormattingCondition(
                FormattingConditionKind.FROM_KEY,
                "person-alpha",
            ),
            style=FormattingStyle(color=FormattingColorToken.BLUE, bold=True),
        ),
        SyntheticFormattingRule(
            rule_key="format-urgent",
            display_name="Synthetic urgent subject",
            order=2,
            condition=FormattingCondition(
                FormattingConditionKind.SUBJECT_CONTAINS_TEXT,
                "urgent",
            ),
            style=FormattingStyle(color=FormattingColorToken.RED, bold=True),
        ),
    )
    validate_formatting_rules(rules)
    return rules


class FormattingMutationAction(StrEnum):
    UPSERT = "UPSERT"
    DELETE = "DELETE"


@dataclass(frozen=True)
class FormattingMutationRequest:
    action: FormattingMutationAction
    rule_key: str
    rule: SyntheticFormattingRule | None = None

    def __post_init__(self) -> None:
        _semantic_token(self.rule_key, "rule_key")
        if self.action is FormattingMutationAction.UPSERT:
            if self.rule is None or self.rule.rule_key != self.rule_key:
                raise ValueError("UPSERT requires a matching synthetic formatting rule")
        elif self.rule is not None:
            raise ValueError("DELETE does not accept rule")

    def to_payload(self) -> dict[str, object]:
        return {
            "action": self.action.value,
            "rule_key": self.rule_key,
            "rule": None if self.rule is None else self.rule.to_projection(),
        }


@dataclass(frozen=True)
class FormattingMutationResult:
    rule_key: str
    action: FormattingMutationAction
    changed: bool
    verified: bool
    read_back: SyntheticFormattingRule | None
    synthetic: bool = True


def list_formatting_rules(
    *,
    readiness: OutlookReadinessReport,
    rules: tuple[SyntheticFormattingRule, ...] | None = None,
) -> tuple[SyntheticFormattingRule, ...]:
    if not readiness.ready_for_readonly_discovery:
        raise ValueError("Outlook read-only discovery is not ready")
    catalog = default_synthetic_formatting_rules() if rules is None else rules
    validate_formatting_rules(catalog)
    return tuple(sorted(catalog, key=lambda item: item.order))


def _read_back(
    rules: tuple[SyntheticFormattingRule, ...],
    rule_key: str,
) -> SyntheticFormattingRule | None:
    matches = tuple(rule for rule in rules if rule.rule_key == rule_key)
    if len(matches) > 1:
        raise RuntimeError("conditional-formatting read-back became ambiguous")
    return matches[0] if matches else None


def _ordered(
    rules: tuple[SyntheticFormattingRule, ...],
) -> tuple[SyntheticFormattingRule, ...]:
    return tuple(
        replace(rule, order=index)
        for index, rule in enumerate(sorted(rules, key=lambda item: item.order), 1)
    )


def _upsert(
    rules: tuple[SyntheticFormattingRule, ...],
    replacement: SyntheticFormattingRule,
) -> tuple[SyntheticFormattingRule, ...]:
    current = _read_back(rules, replacement.rule_key)
    if current is None:
        if replacement.order != len(rules) + 1:
            raise ValueError("new formatting rule must append to the catalog")
        return rules + (replacement,)

    without = [
        rule for rule in sorted(rules, key=lambda item: item.order)
        if rule.rule_key != replacement.rule_key
    ]
    target_index = replacement.order - 1
    if target_index < 0 or target_index > len(without):
        raise ValueError("formatting rule target order is outside the current catalog")
    without.insert(target_index, replacement)
    return tuple(replace(rule, order=index) for index, rule in enumerate(without, 1))


def mutate_formatting_rules(
    rules: tuple[SyntheticFormattingRule, ...],
    request: FormattingMutationRequest,
    *,
    readiness: OutlookReadinessReport,
) -> tuple[tuple[SyntheticFormattingRule, ...], FormattingMutationResult]:
    """Manage synthetic display-only rules with deterministic read-back."""
    if not readiness.ready_for_readonly_discovery:
        raise ValueError("Outlook read-only discovery is not ready")
    validate_formatting_rules(rules)
    current = _read_back(rules, request.rule_key)

    if request.action is FormattingMutationAction.UPSERT:
        assert request.rule is not None
        updated = _upsert(rules, request.rule)
        changed = request.rule != current
    elif current is None:
        updated = rules
        changed = False
    else:
        updated = _ordered(
            tuple(rule for rule in rules if rule.rule_key != request.rule_key)
        )
        changed = True

    validate_formatting_rules(updated)
    read_back = _read_back(updated, request.rule_key)
    if request.action is FormattingMutationAction.UPSERT:
        if read_back != request.rule:
            raise RuntimeError("read-back did not prove conditional-formatting state")
    elif read_back is not None:
        raise RuntimeError("read-back did not prove conditional-formatting deletion")

    return updated, FormattingMutationResult(
        rule_key=request.rule_key,
        action=request.action,
        changed=changed,
        verified=True,
        read_back=read_back,
    )


__all__ = [
    "FormattingColorToken",
    "FormattingCondition",
    "FormattingConditionKind",
    "FormattingMutationAction",
    "FormattingMutationRequest",
    "FormattingMutationResult",
    "FormattingStyle",
    "SyntheticFormattingRule",
    "default_synthetic_formatting_rules",
    "list_formatting_rules",
    "mutate_formatting_rules",
    "validate_formatting_rules",
]
