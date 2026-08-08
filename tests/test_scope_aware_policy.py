from __future__ import annotations

import pytest

from m365_mcp.config import Settings
from m365_mcp.policy import Decision, MetadataPolicyEngine
from m365_mcp.policy_scope import (
    AccountScope,
    MailboxScope,
    PolicyScope,
    ResourceScope,
    canonical_policy_scope,
)
from m365_mcp.tool_registry import default_tool_registry


def test_planner_content_read_derives_reviewed_scope_without_compatibility_break() -> None:
    result = MetadataPolicyEngine().evaluate("planner_task_list", Settings())

    assert result.decision is Decision.ALLOW
    assert result.scope_derived is True
    assert result.scope_reason == "CANONICAL_SCOPE_DERIVED"
    assert result.scope == PolicyScope(
        application="planner",
        surface="planner_web",
        account_scope=AccountScope.PROFESSIONAL_SESSION,
        container_scope="plan",
        mailbox_scope=MailboxScope.NONE,
        resource_scope=ResourceScope.CONTAINER,
    )


def test_explicit_matching_planner_scope_is_verified() -> None:
    definition = default_tool_registry().get("planner_task_get")
    scope = canonical_policy_scope(definition)
    result = MetadataPolicyEngine().evaluate("planner_task_get", Settings(), scope=scope)

    assert result.decision is Decision.ALLOW
    assert result.scope == scope
    assert result.scope_derived is False
    assert result.scope_reason == "SCOPE_VERIFIED"
    assert scope.resource_scope is ResourceScope.RESOURCE


def test_application_scope_mismatch_fails_closed() -> None:
    result = MetadataPolicyEngine().evaluate(
        "planner_plan_list",
        Settings(),
        scope=PolicyScope(
            application="outlook",
            surface="planner_web",
            account_scope=AccountScope.PROFESSIONAL_SESSION,
            container_scope="account",
            resource_scope=ResourceScope.ACCOUNT,
        ),
    )

    assert result.decision is Decision.DENY
    assert result.reason == "SCOPE_APPLICATION_MISMATCH"


def test_account_scope_mismatch_fails_closed() -> None:
    result = MetadataPolicyEngine().evaluate(
        "planner_task_list",
        Settings(),
        scope=PolicyScope(
            application="planner",
            surface="planner_web",
            account_scope=AccountScope.PRODUCT_CONTEXT,
            container_scope="plan",
            resource_scope=ResourceScope.CONTAINER,
        ),
    )

    assert result.decision is Decision.DENY
    assert result.reason == "SCOPE_ACCOUNT_MISMATCH"


def test_container_scope_mismatch_fails_closed() -> None:
    result = MetadataPolicyEngine().evaluate(
        "planner_task_list",
        Settings(),
        scope=PolicyScope(
            application="planner",
            surface="planner_web",
            account_scope=AccountScope.PROFESSIONAL_SESSION,
            container_scope="account",
            resource_scope=ResourceScope.CONTAINER,
        ),
    )

    assert result.decision is Decision.DENY
    assert result.reason == "SCOPE_CONTAINER_MISMATCH"


def test_resource_scope_mismatch_fails_closed() -> None:
    definition = default_tool_registry().get("planner_task_get")
    canonical = canonical_policy_scope(definition)
    result = MetadataPolicyEngine().evaluate(
        "planner_task_get",
        Settings(),
        scope=PolicyScope(
            application=canonical.application,
            surface=canonical.surface,
            account_scope=canonical.account_scope,
            container_scope=canonical.container_scope,
            resource_scope=ResourceScope.CONTAINER,
        ),
    )

    assert result.decision is Decision.DENY
    assert result.reason == "SCOPE_RESOURCE_MISMATCH"


def test_non_outlook_scope_cannot_claim_mailbox_context() -> None:
    with pytest.raises(ValueError, match="mailbox scope is only valid for Outlook"):
        PolicyScope(
            application="planner",
            surface="planner_web",
            account_scope=AccountScope.PROFESSIONAL_SESSION,
            mailbox_scope=MailboxScope.SHARED,
        )


def test_unknown_container_scope_is_rejected_before_policy_evaluation() -> None:
    with pytest.raises(ValueError, match="unknown policy container scope"):
        PolicyScope(
            application="planner",
            surface="planner_web",
            account_scope=AccountScope.PROFESSIONAL_SESSION,
            container_scope="arbitrary-tenant-resource",
        )


def test_scope_cannot_weaken_compatibility_mutation_override() -> None:
    definition = default_tool_registry().get("planner_plan_list")
    scope = canonical_policy_scope(definition)
    result = MetadataPolicyEngine().evaluate(
        "planner_plan_list",
        Settings(),
        mutation=True,
        scope=scope,
    )

    assert result.decision is Decision.DENY
    assert result.reason == "MUTATIONS_DISABLED_IN_0_1_0"
    assert result.scope_reason == "SCOPE_VERIFIED"


def test_all_preserved_planner_tools_receive_bounded_scope_context() -> None:
    engine = MetadataPolicyEngine()
    planner_tools = default_tool_registry().by_application("planner")

    assert len(planner_tools) == 17
    for definition in planner_tools:
        result = engine.evaluate(definition.name, Settings())
        assert result.decision is Decision.ALLOW
        assert result.scope is not None
        assert result.scope.application == "planner"
        assert result.scope.surface == definition.surface
        assert result.scope.mailbox_scope is MailboxScope.NONE
