from __future__ import annotations

import pytest

from m365_mcp.application_registry import (
    ApplicationKey,
    ApplicationState,
    default_application_registry,
)
from m365_mcp.apps.outlook import ooo_message_config, readiness
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


def test_ooo_messages_configure_without_dispatch() -> None:
    current = ooo_message_config.OooMessageSettings()
    desired = ooo_message_config.OooMessageSettings(
        internal_message="Away for a synthetic interval",
        external_message="Unavailable during a synthetic interval",
        external_enabled=True,
    )
    updated, result = ooo_message_config.configure_ooo_messages(
        current,
        desired,
        readiness=_ready(),
    )
    assert updated == desired
    assert result.changed is True
    assert result.verified is True
    assert result.dispatched is False


def test_external_message_requires_explicit_enablement() -> None:
    with pytest.raises(ValueError, match="external_message requires external_enabled"):
        ooo_message_config.OooMessageSettings(external_message="Synthetic external message")


def test_out131_remains_reserved_and_not_public() -> None:
    outlook = default_application_registry().get(ApplicationKey.OUTLOOK)
    assert outlook.state is ApplicationState.RESERVED
    assert default_tool_registry().by_application("outlook") == ()
