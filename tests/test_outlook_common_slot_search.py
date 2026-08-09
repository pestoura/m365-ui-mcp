from __future__ import annotations

import pytest

from m365_mcp.application_registry import (
    ApplicationKey,
    ApplicationState,
    default_application_registry,
)
from m365_mcp.apps.outlook import (
    availability_reads,
    common_slot_search,
    mock_ui,
    readiness,
)
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


def _unready() -> readiness.OutlookReadinessReport:
    return readiness.OutlookReadinessReport(
        state=readiness.OutlookReadinessState.FOUNDATION_READY,
        primary_context_verified=True,
        shared_context_verified=False,
        candidate_count=1,
        observed_count=0,
        blocked_count=0,
        reattestation_count=0,
    )


def _window() -> availability_reads.AvailabilityWindow:
    return availability_reads.AvailabilityWindow(
        from_day_offset=0,
        to_day_offset=0,
        day_start_minute=480,
        day_end_minute=660,
        slot_minutes=60,
    )


def test_common_slot_search_composes_grid_and_excludes_conflicts() -> None:
    result = common_slot_search.find_fixture_common_slots(
        mock_ui.default_outlook_fixture(),
        _window(),
        common_slot_search.CommonSlotRequest(),
        readiness=_ready(),
    )
    assert result.evaluated_slot_count == 3
    assert result.matching_slot_count == 2
    assert len(result.candidates) == 2
    assert all(
        item.feasibility.value == "ALL_FREE" for item in result.candidates
    )
    assert tuple(item.start_minute_of_day for item in result.candidates) == (480, 600)


def test_required_free_is_a_superset_and_truncation_reports_more() -> None:
    fixture = mock_ui.default_outlook_fixture()
    all_free = common_slot_search.find_fixture_common_slots(
        fixture,
        _window(),
        common_slot_search.CommonSlotRequest(
            requirement=common_slot_search.CommonSlotRequirement.ALL_FREE
        ),
        readiness=_ready(),
    )
    required_free = common_slot_search.find_fixture_common_slots(
        fixture,
        _window(),
        common_slot_search.CommonSlotRequest(
            requirement=common_slot_search.CommonSlotRequirement.REQUIRED_FREE
        ),
        readiness=_ready(),
    )
    assert required_free.matching_slot_count >= all_free.matching_slot_count
    limited = common_slot_search.find_fixture_common_slots(
        fixture,
        _window(),
        common_slot_search.CommonSlotRequest(max_results=1),
        readiness=_ready(),
    )
    assert len(limited.candidates) == 1
    assert limited.has_more is True


def test_common_slot_search_rejects_bad_bounds_and_unready() -> None:
    with pytest.raises(ValueError, match="bounded positive count"):
        common_slot_search.CommonSlotRequest(max_results=51)
    with pytest.raises(ValueError, match="not ready"):
        common_slot_search.find_fixture_common_slots(
            mock_ui.default_outlook_fixture(),
            _window(),
            common_slot_search.CommonSlotRequest(),
            readiness=_unready(),
        )


def test_out092_remains_reserved_and_not_public() -> None:
    outlook = default_application_registry().get(ApplicationKey.OUTLOOK)
    assert outlook.state is ApplicationState.RESERVED
    assert default_tool_registry().by_application("outlook") == ()


def test_out092_result_contains_no_live_or_browser_material() -> None:
    result = common_slot_search.find_fixture_common_slots(
        mock_ui.default_outlook_fixture(),
        _window(),
        common_slot_search.CommonSlotRequest(),
        readiness=_ready(),
    )
    rendered = repr(result).lower()
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
