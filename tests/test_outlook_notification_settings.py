from __future__ import annotations

from m365_mcp.application_registry import (
    ApplicationKey,
    ApplicationState,
    default_application_registry,
)
from m365_mcp.apps.outlook import notification_settings, readiness
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


def test_notification_settings_apply_synthetic_desired_state() -> None:
    current = notification_settings.default_synthetic_notification_settings()
    desired = notification_settings.SyntheticNotificationSettings(
        mail_notifications_enabled=False,
        calendar_notifications_enabled=True,
    )
    updated, result = notification_settings.mutate_notification_settings(
        current,
        notification_settings.NotificationMutationRequest(desired),
        readiness=_ready(),
    )
    assert updated == desired
    assert result.read_back == desired
    assert result.changed is True
    assert result.verified is True


def test_notification_no_change_is_idempotent() -> None:
    current = notification_settings.default_synthetic_notification_settings()
    _, result = notification_settings.mutate_notification_settings(
        current,
        notification_settings.NotificationMutationRequest(current),
        readiness=_ready(),
    )
    assert result.changed is False


def test_out072_remains_reserved_and_not_public() -> None:
    outlook = default_application_registry().get(ApplicationKey.OUTLOOK)
    assert outlook.state is ApplicationState.RESERVED
    assert default_tool_registry().by_application("outlook") == ()
