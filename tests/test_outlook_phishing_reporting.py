from __future__ import annotations

import pytest

from m365_mcp.application_registry import (
    ApplicationKey,
    ApplicationState,
    default_application_registry,
)
from m365_mcp.apps.outlook import mock_ui, phishing_reporting, readiness
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


def test_phishing_report_is_governed_and_never_dispatched() -> None:
    intent = phishing_reporting.prepare_phishing_report(
        mock_ui.default_outlook_fixture(),
        phishing_reporting.PhishingReportRequest("msg-001"),
        readiness=_ready(),
    )
    assert intent.report_key == "report-phishing-msg-001"
    assert intent.executable is False
    assert intent.dispatched is False
    assert intent.to_projection()["approval_required"] is True


def test_phishing_report_fails_closed_for_unknown_or_identity_key() -> None:
    with pytest.raises(ValueError, match="synthetic message_key not found"):
        phishing_reporting.prepare_phishing_report(
            mock_ui.default_outlook_fixture(),
            phishing_reporting.PhishingReportRequest("msg-missing"),
            readiness=_ready(),
        )
    with pytest.raises(ValueError, match="address or URL"):
        phishing_reporting.PhishingReportRequest("person@example.test")


def test_out121_remains_reserved_and_not_public() -> None:
    outlook = default_application_registry().get(ApplicationKey.OUTLOOK)
    assert outlook.state is ApplicationState.RESERVED
    assert default_tool_registry().by_application("outlook") == ()
