from __future__ import annotations

from m365_mcp.application_registry import (
    ApplicationKey,
    ApplicationState,
    default_application_registry,
)
from m365_mcp.apps.outlook import automatic_reply_config, readiness
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


def test_automatic_reply_mode_read_and_configure_are_local_only() -> None:
    current = automatic_reply_config.AutomaticReplySettings()
    assert automatic_reply_config.read_automatic_reply_settings(
        current,
        readiness=_ready(),
    ) == current
    updated, result = automatic_reply_config.configure_automatic_reply_mode(
        current,
        automatic_reply_config.AutomaticReplyMode.ENABLED,
        readiness=_ready(),
    )
    assert updated.mode is automatic_reply_config.AutomaticReplyMode.ENABLED
    assert result.changed is True
    assert result.verified is True
    assert result.dispatched is False

    same, again = automatic_reply_config.configure_automatic_reply_mode(
        updated,
        automatic_reply_config.AutomaticReplyMode.ENABLED,
        readiness=_ready(),
    )
    assert same == updated
    assert again.changed is False


def test_out130_remains_reserved_and_not_public() -> None:
    outlook = default_application_registry().get(ApplicationKey.OUTLOOK)
    assert outlook.state is ApplicationState.RESERVED
    assert default_tool_registry().by_application("outlook") == ()
