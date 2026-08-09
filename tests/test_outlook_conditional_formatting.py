from __future__ import annotations

from dataclasses import replace

from m365_mcp.application_registry import (
    ApplicationKey,
    ApplicationState,
    default_application_registry,
)
from m365_mcp.apps.outlook import conditional_formatting, readiness
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


def test_formatting_rules_are_display_only_ordered_and_mutable() -> None:
    rules = conditional_formatting.default_synthetic_formatting_rules()
    listed = conditional_formatting.list_formatting_rules(
        readiness=_ready(),
        rules=rules,
    )
    assert tuple(rule.order for rule in listed) == (1, 2)

    urgent = next(rule for rule in rules if rule.rule_key == "format-urgent")
    updated_rule = replace(
        urgent,
        display_name="Synthetic urgent updated",
        order=1,
        style=conditional_formatting.FormattingStyle(
            color=conditional_formatting.FormattingColorToken.ORANGE,
            bold=True,
        ),
    )
    updated, result = conditional_formatting.mutate_formatting_rules(
        rules,
        conditional_formatting.FormattingMutationRequest(
            conditional_formatting.FormattingMutationAction.UPSERT,
            updated_rule.rule_key,
            updated_rule,
        ),
        readiness=_ready(),
    )
    assert tuple(rule.rule_key for rule in updated) == ("format-urgent", "format-project")
    assert result.read_back == updated_rule
    assert result.verified is True
    assert "selector" not in str(result.read_back.to_projection()).lower()
    assert "css" not in str(result.read_back.to_projection()).lower()


def test_formatting_delete_compacts_order_and_is_idempotent() -> None:
    rules = conditional_formatting.default_synthetic_formatting_rules()
    request = conditional_formatting.FormattingMutationRequest(
        conditional_formatting.FormattingMutationAction.DELETE,
        "format-project",
    )
    rules, first = conditional_formatting.mutate_formatting_rules(
        rules,
        request,
        readiness=_ready(),
    )
    assert first.changed is True
    assert first.read_back is None
    assert tuple(rule.order for rule in rules) == (1,)

    same, repeated = conditional_formatting.mutate_formatting_rules(
        rules,
        request,
        readiness=_ready(),
    )
    assert same == rules
    assert repeated.changed is False


def test_formatting_request_binds_to_idempotency_and_lock() -> None:
    rule = conditional_formatting.default_synthetic_formatting_rules()[0]
    request = conditional_formatting.FormattingMutationRequest(
        conditional_formatting.FormattingMutationAction.UPSERT,
        rule.rule_key,
        rule,
    )
    identity = resource_state_identity(
        ApplicationKey.OUTLOOK,
        account_scope="professional_session",
        container_kind="mail_settings",
        external_container_id="conditional_formatting",
        resource_kind="formatting_rule",
        external_resource_id=request.rule_key,
    )
    record = reserve_operation(
        "outlook_conditional_formatting",
        identity,
        request.to_payload(),
        read_back_required=True,
    )
    lock = state_lock("mock-professional-account", identity)
    assert record.read_back_required is True
    assert lock.state_identity_digest == identity.identity_digest


def test_out068_remains_reserved_and_not_public() -> None:
    outlook = default_application_registry().get(ApplicationKey.OUTLOOK)
    assert outlook.state is ApplicationState.RESERVED
    assert default_tool_registry().by_application("outlook") == ()
