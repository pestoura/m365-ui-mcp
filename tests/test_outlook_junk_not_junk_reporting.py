from __future__ import annotations

import pytest

from m365_mcp.application_registry import (
    ApplicationKey,
    ApplicationState,
    default_application_registry,
)
from m365_mcp.apps.outlook import junk_not_junk_reporting, mock_ui, readiness
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


def test_junk_report_is_governed_and_never_dispatched() -> None:
    intent = junk_not_junk_reporting.prepare_junk_report(
        mock_ui.default_outlook_fixture(),
        junk_not_junk_reporting.JunkReportRequest(
            "msg-001",
            junk_not_junk_reporting.JunkReportAction.JUNK,
        ),
        readiness=_ready(),
    )
    assert intent.report_key == "report-junk-msg-001"
    assert intent.executable is False
    assert intent.dispatched is False
    assert intent.to_projection()["approval_required"] is True


def test_not_junk_is_distinct_and_unknown_message_fails_closed() -> None:
    intent = junk_not_junk_reporting.prepare_junk_report(
        mock_ui.default_outlook_fixture(),
        junk_not_junk_reporting.JunkReportRequest(
            "msg-002",
            junk_not_junk_reporting.JunkReportAction.NOT_JUNK,
        ),
        readiness=_ready(),
    )
    assert intent.report_key == "report-not-junk-msg-002"
    with pytest.raises(ValueError, match="synthetic message_key not found"):
        junk_not_junk_reporting.prepare_junk_report(
            mock_ui.default_outlook_fixture(),
            junk_not_junk_reporting.JunkReportRequest(
                "msg-missing",
                junk_not_junk_reporting.JunkReportAction.JUNK,
            ),
            readiness=_ready(),
        )


def test_out120_remains_reserved_and_not_public() -> None:
    outlook = default_application_registry().get(ApplicationKey.OUTLOOK)
    assert outlook.state is ApplicationState.RESERVED
    assert default_tool_registry().by_application("outlook") == ()
