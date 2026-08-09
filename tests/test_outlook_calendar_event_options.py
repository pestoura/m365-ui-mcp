from __future__ import annotations

import pytest

from m365_mcp.application_registry import (
    ApplicationKey,
    ApplicationState,
    default_application_registry,
)
from m365_mcp.apps.outlook import calendar_event_options, calendar_events, readiness
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


def _event() -> calendar_events.SyntheticEvent:
    return calendar_events.SyntheticEvent(
        event_key="event-001",
        calendar_key="cal-primary",
        subject="Synthetic option target",
        start_day_offset=1,
        start_minute_of_day=600,
        duration_minutes=30,
    )


def _request() -> calendar_event_options.CalendarEventOptionsRequest:
    return calendar_event_options.CalendarEventOptionsRequest(
        event_key="event-001",
        reminder_minutes_before=15,
        category_keys=("category-blue", "category-review"),
        private=True,
        show_as=calendar_events.EventShowAs.TENTATIVE,
    )


def test_event_options_reuse_show_as_and_sensitivity_with_readback() -> None:
    events, options, result = calendar_event_options.mutate_calendar_event_options(
        (_event(),),
        (),
        _request(),
        readiness=_ready(),
    )
    assert result.read_back_event.show_as is calendar_events.EventShowAs.TENTATIVE
    assert result.read_back_event.sensitivity is calendar_events.EventSensitivity.PRIVATE
    assert result.read_back_options.category_keys == (
        "category-blue",
        "category-review",
    )
    assert result.verified is True

    events, options, result = calendar_event_options.mutate_calendar_event_options(
        events,
        options,
        _request(),
        readiness=_ready(),
    )
    assert result.changed is False


def test_event_options_reject_duplicate_categories() -> None:
    with pytest.raises(ValueError, match="unique"):
        calendar_event_options.CalendarEventOptionsRequest(
            event_key="event-001",
            reminder_minutes_before=5,
            category_keys=("category-blue", "category-blue"),
            private=False,
            show_as=calendar_events.EventShowAs.BUSY,
        )


def test_out085_remains_reserved_and_not_public() -> None:
    outlook = default_application_registry().get(ApplicationKey.OUTLOOK)
    assert outlook.state is ApplicationState.RESERVED
    assert default_tool_registry().by_application("outlook") == ()
