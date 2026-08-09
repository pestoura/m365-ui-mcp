"""Synthetic Outlook inbox-rule create/update/delete semantics for OUT-062."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from m365_mcp.apps.outlook.mail_automation_models import (
    SyntheticMailRule,
    validate_rule_catalog,
)
from m365_mcp.apps.outlook.readiness import OutlookReadinessReport


class RuleMutationAction(StrEnum):
    CREATE = "CREATE"
    UPDATE = "UPDATE"
    DELETE = "DELETE"


@dataclass(frozen=True)
class RuleMutationRequest:
    action: RuleMutationAction
    rule_key: str
    rule: SyntheticMailRule | None = None

    def __post_init__(self) -> None:
        if not self.rule_key or self.rule_key != self.rule_key.strip():
            raise ValueError("rule_key must be a non-empty semantic token")
        if any(char.isspace() for char in self.rule_key):
            raise ValueError("rule_key must be a non-empty semantic token")
        if self.action in {RuleMutationAction.CREATE, RuleMutationAction.UPDATE}:
            if self.rule is None or self.rule.rule_key != self.rule_key:
                raise ValueError("CREATE/UPDATE requires a matching synthetic rule")
        elif self.rule is not None:
            raise ValueError("DELETE does not accept rule")

    def to_payload(self) -> dict[str, object]:
        return {
            "action": self.action.value,
            "rule_key": self.rule_key,
            "rule": None if self.rule is None else self.rule.to_projection(),
        }


@dataclass(frozen=True)
class RuleMutationResult:
    rule_key: str
    action: RuleMutationAction
    changed: bool
    verified: bool
    read_back: SyntheticMailRule | None
    synthetic: bool = True


def _read_back(
    rules: tuple[SyntheticMailRule, ...],
    rule_key: str,
) -> SyntheticMailRule | None:
    matches = tuple(rule for rule in rules if rule.rule_key == rule_key)
    if len(matches) > 1:
        raise RuntimeError("synthetic rule read-back became ambiguous")
    return matches[0] if matches else None


def mutate_rules(
    rules: tuple[SyntheticMailRule, ...],
    request: RuleMutationRequest,
    *,
    readiness: OutlookReadinessReport,
    allow_destructive: bool = False,
) -> tuple[tuple[SyntheticMailRule, ...], RuleMutationResult]:
    """Apply one synthetic rule lifecycle mutation with explicit read-back."""
    if not readiness.ready_for_readonly_discovery:
        raise ValueError("Outlook read-only discovery is not ready")
    validate_rule_catalog(rules)
    current = _read_back(rules, request.rule_key)

    if request.action is RuleMutationAction.CREATE:
        assert request.rule is not None
        if current is not None:
            raise ValueError("CREATE requires a new rule_key")
        if request.rule.order != len(rules) + 1:
            raise ValueError("CREATE rule order must append to the catalog")
        if request.rule.destructive and not allow_destructive:
            raise PermissionError("destructive rule action requires explicit policy allowance")
        updated = rules + (request.rule,)
        changed = True
    elif request.action is RuleMutationAction.UPDATE:
        assert request.rule is not None
        if current is None:
            raise ValueError("UPDATE requires an existing rule_key")
        if request.rule.order != current.order or request.rule.enabled != current.enabled:
            raise ValueError("OUT-063 owns rule enable/disable/order changes")
        if (
            request.rule.conditions != current.conditions
            or request.rule.actions != current.actions
            or request.rule.exceptions != current.exceptions
            or request.rule.stop_processing != current.stop_processing
        ):
            raise ValueError("OUT-064 owns rule logic changes")
        updated = tuple(
            request.rule if rule.rule_key == request.rule_key else rule for rule in rules
        )
        changed = request.rule != current
    else:
        if current is None:
            updated = rules
            changed = False
        else:
            remaining = tuple(rule for rule in rules if rule.rule_key != request.rule_key)
            updated = tuple(
                SyntheticMailRule(
                    rule_key=rule.rule_key,
                    display_name=rule.display_name,
                    order=index,
                    conditions=rule.conditions,
                    actions=rule.actions,
                    exceptions=rule.exceptions,
                    enabled=rule.enabled,
                    stop_processing=rule.stop_processing,
                )
                for index, rule in enumerate(sorted(remaining, key=lambda item: item.order), 1)
            )
            changed = True

    validate_rule_catalog(updated)
    read_back = _read_back(updated, request.rule_key)
    if request.action in {RuleMutationAction.CREATE, RuleMutationAction.UPDATE}:
        if read_back != request.rule:
            raise RuntimeError("synthetic read-back did not prove rule lifecycle state")
    elif read_back is not None:
        raise RuntimeError("synthetic read-back did not prove rule deletion")

    return updated, RuleMutationResult(
        rule_key=request.rule_key,
        action=request.action,
        changed=changed,
        verified=True,
        read_back=read_back,
    )


__all__ = [
    "RuleMutationAction",
    "RuleMutationRequest",
    "RuleMutationResult",
    "mutate_rules",
]
