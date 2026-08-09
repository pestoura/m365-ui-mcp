"""Synthetic Outlook rule enable/disable/order semantics for OUT-063."""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import StrEnum

from m365_mcp.apps.outlook.mail_automation_models import (
    SyntheticMailRule,
    validate_rule_catalog,
)
from m365_mcp.apps.outlook.readiness import OutlookReadinessReport


class RuleStateAction(StrEnum):
    ENABLE = "ENABLE"
    DISABLE = "DISABLE"
    MOVE_TO_ORDER = "MOVE_TO_ORDER"


@dataclass(frozen=True)
class RuleStateRequest:
    action: RuleStateAction
    rule_key: str
    target_order: int | None = None

    def __post_init__(self) -> None:
        if (
            not self.rule_key
            or self.rule_key != self.rule_key.strip()
            or any(char.isspace() for char in self.rule_key)
        ):
            raise ValueError("rule_key must be a non-empty semantic token")
        if self.action is RuleStateAction.MOVE_TO_ORDER:
            if self.target_order is None or self.target_order < 1:
                raise ValueError("MOVE_TO_ORDER requires positive target_order")
        elif self.target_order is not None:
            raise ValueError("ENABLE/DISABLE do not accept target_order")

    def to_payload(self) -> dict[str, object]:
        return {
            "action": self.action.value,
            "rule_key": self.rule_key,
            "target_order": self.target_order,
        }


@dataclass(frozen=True)
class RuleStateResult:
    rule_key: str
    action: RuleStateAction
    changed: bool
    verified: bool
    read_back_enabled: bool
    read_back_order: int
    synthetic: bool = True


def _reorder(
    rules: tuple[SyntheticMailRule, ...],
    rule_key: str,
    target_order: int,
) -> tuple[SyntheticMailRule, ...]:
    ordered = list(sorted(rules, key=lambda item: item.order))
    selected = next((rule for rule in ordered if rule.rule_key == rule_key), None)
    if selected is None:
        raise ValueError("synthetic rule_key not found")
    if target_order > len(ordered):
        raise ValueError("target_order exceeds bounded rule catalog")
    ordered.remove(selected)
    ordered.insert(target_order - 1, selected)
    return tuple(replace(rule, order=index) for index, rule in enumerate(ordered, 1))


def mutate_rule_state(
    rules: tuple[SyntheticMailRule, ...],
    request: RuleStateRequest,
    *,
    readiness: OutlookReadinessReport,
) -> tuple[tuple[SyntheticMailRule, ...], RuleStateResult]:
    """Change only enabled state or ordering, then verify through read-back."""
    if not readiness.ready_for_readonly_discovery:
        raise ValueError("Outlook read-only discovery is not ready")
    validate_rule_catalog(rules)
    current = next((rule for rule in rules if rule.rule_key == request.rule_key), None)
    if current is None:
        raise ValueError("synthetic rule_key not found")

    if request.action is RuleStateAction.ENABLE:
        updated = tuple(
            replace(rule, enabled=True) if rule.rule_key == request.rule_key else rule
            for rule in rules
        )
    elif request.action is RuleStateAction.DISABLE:
        updated = tuple(
            replace(rule, enabled=False) if rule.rule_key == request.rule_key else rule
            for rule in rules
        )
    else:
        assert request.target_order is not None
        updated = _reorder(rules, request.rule_key, request.target_order)

    validate_rule_catalog(updated)
    read_back = next(rule for rule in updated if rule.rule_key == request.rule_key)
    changed = updated != rules

    expected_enabled = (
        True
        if request.action is RuleStateAction.ENABLE
        else False
        if request.action is RuleStateAction.DISABLE
        else current.enabled
    )
    expected_order = (
        request.target_order
        if request.action is RuleStateAction.MOVE_TO_ORDER
        else current.order
    )
    if read_back.enabled != expected_enabled or read_back.order != expected_order:
        raise RuntimeError("synthetic read-back did not prove rule state/order mutation")

    return updated, RuleStateResult(
        rule_key=request.rule_key,
        action=request.action,
        changed=changed,
        verified=True,
        read_back_enabled=read_back.enabled,
        read_back_order=read_back.order,
    )


__all__ = [
    "RuleStateAction",
    "RuleStateRequest",
    "RuleStateResult",
    "mutate_rule_state",
]
