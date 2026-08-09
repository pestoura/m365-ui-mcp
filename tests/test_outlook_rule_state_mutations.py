from __future__ import annotations

from m365_mcp.application_registry import (
    ApplicationKey,
    ApplicationState,
    default_application_registry,
)
from m365_mcp.apps.outlook import (
    mail_automation_models,
    readiness,
    rule_state_mutations,
)
from m365_mcp.idempotency_v2 import reserve_operation
from m365_mcp.state_identity import resource_state_identity
from m365_mcp.tool_registry import default_tool_registry
from m365_mcp.typed_locks import state_lock


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


def test_rule_enable_disable_are_idempotent_and_verified() -> None:
    rules = mail_automation_models.default_synthetic_rules()
    rules, disabled = rule_state_mutations.mutate_rule_state(
        rules,
        rule_state_mutations.RuleStateRequest(
            rule_state_mutations.RuleStateAction.DISABLE,
            "rule-project",
        ),
        readiness=_ready(),
    )
    assert disabled.changed is True
    assert disabled.read_back_enabled is False

    same, repeated = rule_state_mutations.mutate_rule_state(
        rules,
        rule_state_mutations.RuleStateRequest(
            rule_state_mutations.RuleStateAction.DISABLE,
            "rule-project",
        ),
        readiness=_ready(),
    )
    assert same == rules
    assert repeated.changed is False

    enabled_rules, enabled = rule_state_mutations.mutate_rule_state(
        rules,
        rule_state_mutations.RuleStateRequest(
            rule_state_mutations.RuleStateAction.ENABLE,
            "rule-project",
        ),
        readiness=_ready(),
    )
    assert enabled_rules[0].enabled is True
    assert enabled.read_back_enabled is True


def test_rule_order_move_reindexes_catalog_contiguously() -> None:
    rules = mail_automation_models.default_synthetic_rules()
    updated, result = rule_state_mutations.mutate_rule_state(
        rules,
        rule_state_mutations.RuleStateRequest(
            rule_state_mutations.RuleStateAction.MOVE_TO_ORDER,
            "rule-followup",
            target_order=1,
        ),
        readiness=_ready(),
    )
    assert tuple(rule.rule_key for rule in updated) == ("rule-followup", "rule-project")
    assert tuple(rule.order for rule in updated) == (1, 2)
    assert result.read_back_order == 1
    assert result.verified is True


def test_rule_state_request_binds_to_idempotency_and_lock() -> None:
    request = rule_state_mutations.RuleStateRequest(
        rule_state_mutations.RuleStateAction.MOVE_TO_ORDER,
        "rule-followup",
        target_order=1,
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
        "outlook_rule_state_order",
        identity,
        request.to_payload(),
        read_back_required=True,
    )
    lock = state_lock("mock-professional-account", identity)
    assert record.read_back_required is True
    assert lock.state_identity_digest == identity.identity_digest


def test_out063_remains_reserved_and_not_public() -> None:
    outlook = default_application_registry().get(ApplicationKey.OUTLOOK)
    assert outlook.state is ApplicationState.RESERVED
    assert default_tool_registry().by_application("outlook") == ()
