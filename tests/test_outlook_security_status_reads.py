from __future__ import annotations

import pytest

from m365_mcp.application_registry import (
    ApplicationKey,
    ApplicationState,
    default_application_registry,
)
from m365_mcp.apps.outlook import mock_ui, readiness, security_status_reads
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


def test_security_status_is_synthetic_and_live_unobserved() -> None:
    status = security_status_reads.read_message_security_status(
        mock_ui.default_outlook_fixture(),
        "msg-002",
        readiness=_ready(),
    )
    assert status.sensitivity is security_status_reads.SensitivityStatus.CONFIDENTIAL
    assert status.protection is security_status_reads.MessageProtectionStatus.PROTECTED_SYNTHETIC
    assert status.source == "SYNTHETIC_FIXTURE"
    assert status.live_support_state == "UNOBSERVED"
    assert status.to_projection()["synthetic"] is True


def test_security_status_rejects_unknown_message() -> None:
    with pytest.raises(ValueError, match="synthetic message_key not found"):
        security_status_reads.read_message_security_status(
            mock_ui.default_outlook_fixture(),
            "msg-missing",
            readiness=_ready(),
        )


def test_out124_remains_reserved_and_not_public() -> None:
    outlook = default_application_registry().get(ApplicationKey.OUTLOOK)
    assert outlook.state is ApplicationState.RESERVED
    assert default_tool_registry().by_application("outlook") == ()
