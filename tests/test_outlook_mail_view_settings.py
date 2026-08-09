from __future__ import annotations

from m365_mcp.application_registry import (
    ApplicationKey,
    ApplicationState,
    default_application_registry,
)
from m365_mcp.apps.outlook import mail_view_settings, readiness
from m365_mcp.tool_registry import default_tool_registry


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


def test_mail_view_settings_apply_focused_and_conversation_preferences() -> None:
    current = mail_view_settings.default_synthetic_mail_view_settings()
    desired = mail_view_settings.SyntheticMailViewSettings(
        focused_inbox_enabled=False,
        conversation_view_enabled=True,
        conversation_sort=mail_view_settings.ConversationSort.OLDEST_FIRST,
    )
    updated, result = mail_view_settings.mutate_mail_view_settings(
        current,
        mail_view_settings.MailViewMutationRequest(desired),
        readiness=_ready(),
    )
    assert updated == desired
    assert result.read_back == desired
    assert result.changed is True
    assert result.verified is True


def test_mail_view_no_change_is_idempotent() -> None:
    current = mail_view_settings.default_synthetic_mail_view_settings()
    _, result = mail_view_settings.mutate_mail_view_settings(
        current,
        mail_view_settings.MailViewMutationRequest(current),
        readiness=_ready(),
    )
    assert result.changed is False


def test_out071_remains_reserved_and_not_public() -> None:
    outlook = default_application_registry().get(ApplicationKey.OUTLOOK)
    assert outlook.state is ApplicationState.RESERVED
    assert default_tool_registry().by_application("outlook") == ()
