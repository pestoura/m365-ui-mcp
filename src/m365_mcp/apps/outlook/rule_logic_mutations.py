"""Synthetic Outlook rule conditions/actions/exceptions/stop-processing for OUT-064."""

from __future__ import annotations

from dataclasses import dataclass, replace

from m365_mcp.apps.outlook.mail_automation_models import (
    RuleAction,
    RulePredicate,
    SyntheticMailRule,
    validate_rule_catalog,
)
from m365_mcp.apps.outlook.readiness import OutlookReadinessReport


@dataclass(frozen=True)
class RuleLogicRequest:
    rule_key: str
    conditions: tuple[RulePredicate, ...] | None = None
    actions: tuple[RuleAction, ...] | None = None
    exceptions: tuple[RulePredicate, ...] | None = None
    stop_processing: bool | None = None

    def __post_init__(self) -> None:
        if (
            not self.rule_key
            or self.rule_key != self.rule_key.strip()
            or any(char.isspace() for char in self.rule_key)
        ):
            raise ValueError("rule_key must be a non-empty semantic token")
        if all(
            value is None
            for value in (
                self.conditions,
                self.actions,
                self.exceptions,
                self.stop_processing,
            )
        ):
            raise ValueError("at least one rule-logic dimension is required")
        if self.conditions is not None and not self.conditions:
            raise ValueError("conditions must not be empty")
        if self.actions is not None and not self.actions:
            raise ValueError("actions must not be empty")

    def to_payload(self) -> dict[str, object]:
        return {
            "rule_key": self.rule_key,
            "conditions": (
                None
                if self.conditions is None
                else [item.to_projection() for item in self.conditions]
            ),
            "actions": (
                None
                if self.actions is None
                else [item.to_projection() for item in self.actions]
            ),
            "exceptions": (
                None
                if self.exceptions is None
                else [item.to_projection() for item in self.exceptions]
            ),
            "stop_processing": self.stop_processing,
        }


@dataclass(frozen=True)
class RuleLogicResult:
    rule_key: str
    changed: bool
    verified: bool
    destructive: bool
    read_back: SyntheticMailRule
    synthetic: bool = True


def mutate_rule_logic(
    rules: tuple[SyntheticMailRule, ...],
    request: RuleLogicRequest,
    *,
    readiness: OutlookReadinessReport,
    allow_destructive: bool = False,
) -> tuple[tuple[SyntheticMailRule, ...], RuleLogicResult]:
    """Update only rule logic and verify the resulting synthetic rule through read-back."""
    if not readiness.ready_for_readonly_discovery:
        raise ValueError("Outlook read-only discovery is not ready")
    validate_rule_catalog(rules)
    current = next((rule for rule in rules if rule.rule_key == request.rule_key), None)
    if current is None:
        raise ValueError("synthetic rule_key not found")

    replacement = replace(
        current,
        conditions=current.conditions if request.conditions is None else request.conditions,
        actions=current.actions if request.actions is None else request.actions,
        exceptions=current.exceptions if request.exceptions is None else request.exceptions,
        stop_processing=(
            current.stop_processing
            if request.stop_processing is None
            else request.stop_processing
        ),
    )
    if replacement.destructive and not allow_destructive:
        raise PermissionError("destructive rule action requires explicit policy allowance")

    updated = tuple(
        replacement if rule.rule_key == request.rule_key else rule for rule in rules
    )
    validate_rule_catalog(updated)
    read_back = next(rule for rule in updated if rule.rule_key == request.rule_key)
    if read_back != replacement:
        raise RuntimeError("synthetic read-back did not prove rule logic mutation")

    return updated, RuleLogicResult(
        rule_key=request.rule_key,
        changed=replacement != current,
        verified=True,
        destructive=replacement.destructive,
        read_back=read_back,
    )


__all__ = ["RuleLogicRequest", "RuleLogicResult", "mutate_rule_logic"]
