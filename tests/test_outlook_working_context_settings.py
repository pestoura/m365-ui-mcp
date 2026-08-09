from __future__ import annotations

import pytest

from m365_mcp.application_registry import (
    ApplicationKey,
    ApplicationState,
    default_application_registry,
)
from m365_mcp.apps.outlook import mock_ui, readiness, working_context_settings
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


def _desired() -> working_context_settings.WorkingContextSettings:
    return working_context_settings.WorkingContextSettings(
        time_zone_key="EUROPE_WEST",
        working_hours=working_context_settings.WorkingHours((0, 1, 2, 3, 4), 480, 960),
        work_location=working_context_settings.WorkLocationKind.HYBRID,
    )


def test_working_context_update_is_exact_read_back_and_idempotent() -> None:
    fixture = mock_ui.default_outlook_fixture()
    updated, result = working_context_settings.apply_working_context_settings(
        fixture,
        _desired(),
        readiness=_ready(),
    )
    assert result.changed is True
    assert result.verified is True
    assert result.read_back == _desired()
    _, repeat = working_context_settings.apply_working_context_settings(
        fixture,
        _desired(),
        readiness=_ready(),
        settings=updated,
    )
    assert repeat.changed is False


def test_working_hours_and_timezone_fail_closed() -> None:
    with pytest.raises(ValueError, match="0..6"):
        working_context_settings.WorkingHours((0, 7), 480, 960)
    with pytest.raises(ValueError, match="positive interval"):
        working_context_settings.WorkingHours((0, 1), 960, 480)
    with pytest.raises(ValueError, match="semantic key"):
        working_context_settings.WorkingContextSettings(
            time_zone_key="https://example.invalid/timezone",
            working_hours=working_context_settings.WorkingHours((0,), 480, 960),
            work_location=working_context_settings.WorkLocationKind.REMOTE,
        )


def test_out098_remains_reserved_and_not_public() -> None:
    outlook = default_application_registry().get(ApplicationKey.OUTLOOK)
    assert outlook.state is ApplicationState.RESERVED
    assert default_tool_registry().by_application("outlook") == ()


def test_out098_projection_contains_no_location_or_session_material() -> None:
    projection = _desired().to_projection()
    rendered = repr(projection).lower()
    assert "address" not in rendered
    for marker in (
        "https://",
        "http://",
        "selector",
        "xpath",
        "css=",
        "cookie",
        "token",
        "graph.microsoft",
        "@",
    ):
        assert marker not in rendered
