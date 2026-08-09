from __future__ import annotations

from dataclasses import replace

import pytest

from m365_mcp.application_registry import (
    ApplicationKey,
    ApplicationState,
    default_application_registry,
)
from m365_mcp.apps.outlook import mail_automation_models, readiness, rule_mutations
from m365_mcp.idempotency_v2 import reserve_operation
from m365_mcp.state_identity import resource_state_identity
from m365_mcp.tool_registry import default_tool_registry
from m365_mcp.typed_locks import state_lock

# Cumulative revalidation trigger: OUT-060..061 integrated in Wave G.


def _ready() -> readiness.OutlookReadinessReport:
    return readiness.OutlookReadinessReport(
        state=readiness.OutlookReadinessState.DISCOVERY_READY,
        primary_context_verified=True,
        shared_context_verified=False,
        candidate_count=1,
        observed_count=1,
        blocked_count=0,
        reattestation_count=0,
    )


def _new_rule(*, destructive: bool = False) -> mail_automation_models.SyntheticMailRule:
    action = (
        mail_automation_models.RuleAction(mail_automation_models.RuleActionKind.DELETE)
        if destructive
        else mail_automation_models.RuleAction(
            mail_automation_models.RuleActionKind.MARK_READ
        )
    )
    return mail_automation_models.SyntheticMailRule(
        rule_key="rule-third",
        display_name="Synthetic third rule",
        order=3,
        conditions=(
            mail_automation_models.RulePredicate(
                mail_automation_models.RuleConditionKind.FROM_KEY,
                "person-beta",
            ),
        ),
        actions=(action,),
    )


def test_rule_create_and_display_name_update_have_readback() -> None:
    rules = mail_automation_models.default_synthetic_rules()
    created_rule = _new_rule()
    rules, created = rule_mutations.mutate_rules(
        rules,
        rule_mutations.RuleMutationRequest(
            rule_mutations.RuleMutationAction.CREATE,
            created_rule.rule_key,
            created_rule,
        ),
        readiness=_ready(),
    )
    assert created.verified is True
    assert created.read_back == created_rule

    renamed = replace(created_rule, display_name="Synthetic renamed rule")
    rules, updated = rule_mutations.mutate_rules(
        rules,
        rule_mutations.RuleMutationRequest(
            rule_mutations.RuleMutationAction.UPDATE,
            renamed.rule_key,
            renamed,
        ),
        readiness=_ready(),
    )
    assert updated.changed is True
    assert updated.read_back == renamed


def test_rule_update_cannot_bypass_state_order_or_logic_owners() -> None:
    rules = mail_automation_models.default_synthetic_rules()
    current = rules[0]

    with pytest.raises(ValueError, match="OUT-063 owns"):
        rule_mutations.mutate_rules(
            rules,
            rule_mutations.RuleMutationRequest(
                rule_mutations.RuleMutationAction.UPDATE,
                current.rule_key,
                replace(current, enabled=False),
            ),
            readiness=_ready(),
        )

    with pytest.raises(ValueError, match="OUT-064 owns"):
        rule_mutations.mutate_rules(
            rules,
            rule_mutations.RuleMutationRequest(
                rule_mutations.RuleMutationAction.UPDATE,
                current.rule_key,
                replace(current, stop_processing=not current.stop_processing),
            ),
            readiness=_ready(),
        )


def test_rule_delete_compacts_order_and_is_idempotent() -> None:
    rules = mail_automation_models.default_synthetic_rules() + (_new_rule(),)
    rules, deleted = rule_mutations.mutate_rules(
        rules,
        rule_mutations.RuleMutationRequest(
            rule_mutations.RuleMutationAction.DELETE,
            "rule-project",
        ),
        readiness=_ready(),
    )
    assert deleted.changed is True
    assert deleted.read_back is None
    assert tuple(rule.order for rule in rules) == (1, 2)

    same, repeated = rule_mutations.mutate_rules(
        rules,
        rule_mutations.RuleMutationRequest(
            rule_mutations.RuleMutationAction.DELETE,
            "rule-project",
        ),
        readiness=_ready(),
    )
    assert same == rules
    assert repeated.changed is False


def test_destructive_create_requires_explicit_policy_allowance() -> None:
    request = rule_mutations.RuleMutationRequest(
        rule_mutations.RuleMutationAction.CREATE,
        "rule-third",
        _new_rule(destructive=True),
    )
    with pytest.raises(PermissionError, match="explicit policy allowance"):
        rule_mutations.mutate_rules(
            mail_automation_models.default_synthetic_rules(),
            request,
            readiness=_ready(),
        )


def test_rule_request_binds_to_idempotency_and_lock() -> None:
    request = rule_mutations.RuleMutationRequest(
        rule_mutations.RuleMutationAction.DELETE,
        "rule-project",
    )
    identity = resource_state_identity(
        ApplicationKey.OUTLOOK,
        account_scope="professional_session",
        container_kind="mail_settings",
        external_container_id="rules",
        resource_kind="mail_rule",
        external_resource_id=request.rule_key,
    )
    record = reserve_operation(
        "outlook_rule_lifecycle",
        identity,
        request.to_payload(),
        read_back_required=True,
    )
    lock = state_lock("mock-professional-account", identity)
    assert record.read_back_required is True
    assert lock.state_identity_digest == identity.identity_digest


def test_out062_remains_reserved_and_not_public() -> None:
    outlook = default_application_registry().get(ApplicationKey.OUTLOOK)
    assert outlook.state is ApplicationState.RESERVED
    assert default_tool_registry().by_application("outlook") == ()
