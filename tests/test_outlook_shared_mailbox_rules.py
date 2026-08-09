from __future__ import annotations

import pytest

from m365_mcp.application_registry import (
    ApplicationKey,
    ApplicationState,
    default_application_registry,
)
from m365_mcp.apps.outlook import (
    mail_automation_models,
    readiness,
    rule_mutations,
    shared_mailbox_context,
    shared_mailbox_rules,
)
from m365_mcp.tool_registry import default_tool_registry


def _ready() -> readiness.OutlookReadinessReport:
    return readiness.OutlookReadinessReport(
        state=readiness.OutlookReadinessState.DISCOVERY_READY,
        primary_context_verified=True,
        shared_context_verified=True,
        candidate_count=1,
        observed_count=1,
        blocked_count=0,
        reattestation_count=0,
    )


def _context(*, valid: bool) -> shared_mailbox_context.SharedMailboxContext:
    return shared_mailbox_context.SharedMailboxContext(
        state=(
            shared_mailbox_context.SharedMailboxContextState.VERIFIED
            if valid
            else shared_mailbox_context.SharedMailboxContextState.UNVERIFIED
        ),
        primary_context_verified=True,
        shared_shell_verified=valid,
        scope_digest="a" * 64 if valid else None,
        evidence_digest="b" * 64 if valid else None,
    )


def test_shared_rule_reads_and_mutations_reuse_existing_semantics() -> None:
    rules = mail_automation_models.default_synthetic_rules()
    listing = shared_mailbox_rules.list_shared_mailbox_rules(
        _context(valid=True),
        readiness=_ready(),
        rules=rules,
    )
    assert listing.rule_count == len(rules)
    first = listing.rules[0]
    assert (
        shared_mailbox_rules.get_shared_mailbox_rule(
            _context(valid=True),
            first.rule_key,
            readiness=_ready(),
            rules=rules,
        )
        == first
    )
    updated, result = shared_mailbox_rules.mutate_shared_mailbox_rules(
        _context(valid=True),
        rules,
        rule_mutations.RuleMutationRequest(
            rule_mutations.RuleMutationAction.DELETE,
            "rule-missing",
        ),
        readiness=_ready(),
    )
    assert updated == rules
    assert result.changed is False
    assert result.verified is True


def test_shared_rule_operations_fail_closed_without_verified_scope() -> None:
    with pytest.raises(ValueError, match="verified shared mailbox context"):
        shared_mailbox_rules.list_shared_mailbox_rules(
            _context(valid=False),
            readiness=_ready(),
        )


def test_out114_remains_reserved_and_not_public() -> None:
    outlook = default_application_registry().get(ApplicationKey.OUTLOOK)
    assert outlook.state is ApplicationState.RESERVED
    assert default_tool_registry().by_application("outlook") == ()
