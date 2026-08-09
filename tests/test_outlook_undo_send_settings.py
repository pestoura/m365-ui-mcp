from __future__ import annotations

import pytest

from m365_mcp.application_registry import (
    ApplicationKey,
    ApplicationState,
    default_application_registry,
)
from m365_mcp.apps.outlook import readiness, undo_send_settings
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


def test_undo_send_settings_apply_and_read_back() -> None:
    current = undo_send_settings.default_synthetic_undo_send_settings()
    desired = undo_send_settings.SyntheticUndoSendSettings(
        enabled=True,
        delay_seconds=7,
    )
    updated, result = undo_send_settings.mutate_undo_send_settings(
        current,
        undo_send_settings.UndoSendMutationRequest(desired),
        readiness=_ready(),
    )
    assert updated == desired
    assert result.read_back == desired
    assert result.changed is True
    assert result.verified is True


def test_undo_send_validation_is_model_based_not_live_limit_claim() -> None:
    with pytest.raises(ValueError, match="disabled Undo Send requires zero delay"):
        undo_send_settings.SyntheticUndoSendSettings(enabled=False, delay_seconds=1)
    with pytest.raises(ValueError, match="positive delay"):
        undo_send_settings.SyntheticUndoSendSettings(enabled=True, delay_seconds=0)


def test_out070_remains_reserved_and_not_public() -> None:
    outlook = default_application_registry().get(ApplicationKey.OUTLOOK)
    assert outlook.state is ApplicationState.RESERVED
    assert default_tool_registry().by_application("outlook") == ()
