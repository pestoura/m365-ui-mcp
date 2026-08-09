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
    rule_logic_mutations,
)
from m365_mcp.idempotency_v2 import reserve_operation
from m365_mcp.state_identity import resource_state_identity
from m365_mcp.tool_registry import default_tool_registry
from m365_mcp.typed_locks import state_lock

# Cumulative revalidation trigger: OUT-060..063 integrated in Wave G.


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


def test_rule_logic_updates_conditions_actions_exceptions_and_stop_processing() -> None:
    rules = mail_automation_models.default_synthetic_rules()
    request = rule_logic_mutations.RuleLogicRequest(
        rule_key="rule-followup",
        conditions=(
            mail_automation_models.RulePredicate(
                mail_automation_models.RuleConditionKind.FROM_KEY,
                "person-beta",
            ),
            mail_automation_models.RulePredicate(
                mail_automation_models.RuleConditionKind.HAS_ATTACHMENT,
            ),
        ),
        actions=(
            mail_automation_models.RuleAction(
                mail_automation_models.RuleActionKind.MOVE_TO_FOLDER,
                "archive",
            ),
        ),
        exceptions=(
            mail_automation_models.RulePredicate(
                mail_automation_models.RuleConditionKind.SUBJECT_CONTAINS_TEXT,
                "keep",
            ),
        ),
        stop_processing=True,
    )
    updated, result = rule_logic_mutations.mutate_rule_logic(
        rules,
        request,
        readiness=_ready(),
    )
    selected = next(rule for rule in updated if rule.rule_key == "rule-followup")
    assert len(selected.conditions) == 2
    assert selected.actions[0].target_key == "archive"
    assert selected.exceptions[0].value_key == "keep"
    assert selected.stop_processing is True
    assert result.read_back == selected
    assert result.verified is True


def test_rule_logic_requires_non_empty_conditions_and_actions() -> None:
    with pytest.raises(ValueError, match="conditions must not be empty"):
        rule_logic_mutations.RuleLogicRequest("rule-project", conditions=())
    with pytest.raises(ValueError, match="actions must not be empty"):
        rule_logic_mutations.RuleLogicRequest("rule-project", actions=())


def test_destructive_logic_requires_explicit_policy_allowance() -> None:
    request = rule_logic_mutations.RuleLogicRequest(
        rule_key="rule-followup",
        actions=(
            mail_automation_models.RuleAction(
                mail_automation_models.RuleActionKind.DELETE,
            ),
        ),
    )
    with pytest.raises(PermissionError, match="explicit policy allowance"):
        rule_logic_mutations.mutate_rule_logic(
            mail_automation_models.default_synthetic_rules(),
            request,
            readiness=_ready(),
        )

    updated, result = rule_logic_mutations.mutate_rule_logic(
        mail_automation_models.default_synthetic_rules(),
        request,
        readiness=_ready(),
        allow_destructive=True,
    )
    selected = next(rule for rule in updated if rule.rule_key == "rule-followup")
    assert selected.destructive is True
    assert result.destructive is True


def test_rule_logic_request_binds_to_idempotency_and_lock() -> None:
    request = rule_logic_mutations.RuleLogicRequest(
        rule_key="rule-project",
        stop_processing=False,
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
        "outlook_rule_logic",
        identity,
        request.to_payload(),
        read_back_required=True,
    )
    lock = state_lock("mock-professional-account", identity)
    assert record.read_back_required is True
    assert lock.state_identity_digest == identity.identity_digest


def test_out064_remains_reserved_and_not_public() -> None:
    outlook = default_application_registry().get(ApplicationKey.OUTLOOK)
    assert outlook.state is ApplicationState.RESERVED
    assert default_tool_registry().by_application("outlook") == ()
