"""Synthetic Outlook inbox-rule list/get reads for OUT-061."""

from __future__ import annotations

from dataclasses import dataclass

from m365_mcp.apps.outlook.mail_automation_models import (
    SyntheticMailRule,
    default_synthetic_rules,
    validate_rule_catalog,
)
from m365_mcp.apps.outlook.readiness import OutlookReadinessReport


@dataclass(frozen=True)
class RuleListResult:
    rules: tuple[SyntheticMailRule, ...]
    rule_count: int
    enabled_count: int
    destructive_count: int
    synthetic: bool = True

    def to_projection(self) -> dict[str, object]:
        return {
            "rules": [rule.to_projection() for rule in self.rules],
            "rule_count": self.rule_count,
            "enabled_count": self.enabled_count,
            "destructive_count": self.destructive_count,
            "synthetic": True,
        }


def list_rules(
    *,
    readiness: OutlookReadinessReport,
    rules: tuple[SyntheticMailRule, ...] | None = None,
) -> RuleListResult:
    """List a bounded synthetic rule catalog in execution order."""
    if not readiness.ready_for_readonly_discovery:
        raise ValueError("Outlook read-only discovery is not ready")
    catalog = default_synthetic_rules() if rules is None else rules
    validate_rule_catalog(catalog)
    ordered = tuple(sorted(catalog, key=lambda rule: rule.order))
    return RuleListResult(
        rules=ordered,
        rule_count=len(ordered),
        enabled_count=sum(1 for rule in ordered if rule.enabled),
        destructive_count=sum(1 for rule in ordered if rule.destructive),
    )


def get_rule(
    rule_key: str,
    *,
    readiness: OutlookReadinessReport,
    rules: tuple[SyntheticMailRule, ...] | None = None,
) -> SyntheticMailRule:
    """Resolve exactly one synthetic rule by semantic key."""
    listing = list_rules(readiness=readiness, rules=rules)
    matches = tuple(rule for rule in listing.rules if rule.rule_key == rule_key)
    if len(matches) != 1:
        raise ValueError("rule_key must resolve to exactly one synthetic rule")
    return matches[0]


__all__ = ["RuleListResult", "get_rule", "list_rules"]
