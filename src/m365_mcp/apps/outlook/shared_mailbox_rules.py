"""Shared-mailbox-scoped synthetic rule semantics for OUT-114."""

from __future__ import annotations

from m365_mcp.apps.outlook.mail_automation_models import SyntheticMailRule
from m365_mcp.apps.outlook.readiness import OutlookReadinessReport
from m365_mcp.apps.outlook.rule_mutations import (
    RuleMutationRequest,
    RuleMutationResult,
    mutate_rules,
)
from m365_mcp.apps.outlook.rule_reads import RuleListResult, get_rule, list_rules
from m365_mcp.apps.outlook.shared_mailbox_context import SharedMailboxContext


def _gate(context: SharedMailboxContext) -> None:
    if not context.valid:
        raise ValueError("verified shared mailbox context is required")


def list_shared_mailbox_rules(
    context: SharedMailboxContext,
    *,
    readiness: OutlookReadinessReport,
    rules: tuple[SyntheticMailRule, ...] | None = None,
) -> RuleListResult:
    _gate(context)
    return list_rules(readiness=readiness, rules=rules)


def get_shared_mailbox_rule(
    context: SharedMailboxContext,
    rule_key: str,
    *,
    readiness: OutlookReadinessReport,
    rules: tuple[SyntheticMailRule, ...] | None = None,
) -> SyntheticMailRule:
    _gate(context)
    return get_rule(rule_key, readiness=readiness, rules=rules)


def mutate_shared_mailbox_rules(
    context: SharedMailboxContext,
    rules: tuple[SyntheticMailRule, ...],
    request: RuleMutationRequest,
    *,
    readiness: OutlookReadinessReport,
    allow_destructive: bool = False,
) -> tuple[tuple[SyntheticMailRule, ...], RuleMutationResult]:
    _gate(context)
    return mutate_rules(
        rules,
        request,
        readiness=readiness,
        allow_destructive=allow_destructive,
    )


__all__ = [
    "get_shared_mailbox_rule",
    "list_shared_mailbox_rules",
    "mutate_shared_mailbox_rules",
]
