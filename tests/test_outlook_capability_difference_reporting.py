from __future__ import annotations

import pytest

from m365_mcp.application_registry import (
    ApplicationKey,
    ApplicationState,
    default_application_registry,
)
from m365_mcp.apps.outlook import capability_difference_reporting
from m365_mcp.tool_registry import default_tool_registry


def test_capability_report_is_closed_explicit_and_live_unobserved() -> None:
    report = capability_difference_reporting.report_capability_difference(
        capability_difference_reporting.CapabilityKind.OUTBOUND_SEND
    )
    assert (
        report.shared_mailbox
        is capability_difference_reporting.CapabilitySurfaceState.GOVERNED_NOT_EXECUTABLE
    )
    assert (
        report.delegated_send
        is capability_difference_reporting.CapabilitySurfaceState.GOVERNED_NOT_EXECUTABLE
    )
    assert report.live_support_state == "UNOBSERVED"
    assert report.synthetic is True


def test_calendar_read_reports_permission_scoped_shared_surface() -> None:
    report = capability_difference_reporting.report_capability_difference(
        capability_difference_reporting.CapabilityKind.CALENDAR_READ
    )
    assert (
        report.shared_calendar
        is capability_difference_reporting.CapabilitySurfaceState.PERMISSION_SCOPED
    )
    assert (
        report.delegated_send
        is capability_difference_reporting.CapabilitySurfaceState.NOT_AVAILABLE
    )


def test_unknown_capability_fails_closed() -> None:
    with pytest.raises(ValueError, match="closed CapabilityKind"):
        capability_difference_reporting.report_capability_difference("MAIL_READ")  # type: ignore[arg-type]


def test_out119_remains_reserved_and_not_public() -> None:
    outlook = default_application_registry().get(ApplicationKey.OUTLOOK)
    assert outlook.state is ApplicationState.RESERVED
    assert default_tool_registry().by_application("outlook") == ()
