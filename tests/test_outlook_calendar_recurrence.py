from __future__ import annotations

import pytest

from m365_mcp.application_registry import (
    ApplicationKey,
    ApplicationState,
    default_application_registry,
)
from m365_mcp.apps.outlook import calendar_recurrence, readiness
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


def _series() -> calendar_recurrence.SyntheticRecurrenceSeries:
    return calendar_recurrence.SyntheticRecurrenceSeries(
        series_key="series-001",
        anchor_event_key="event-001",
        frequency=calendar_recurrence.RecurrenceFrequency.WEEKLY,
        interval=1,
        occurrence_count=3,
    )


def test_recurrence_upsert_exposes_deterministic_occurrence_keys() -> None:
    request = calendar_recurrence.RecurrenceMutationRequest(
        calendar_recurrence.RecurrenceMutationAction.UPSERT,
        series=_series(),
    )
    series, result = calendar_recurrence.mutate_recurrence_series(
        (), request, readiness=_ready()
    )
    assert series == (_series(),)
    assert result.occurrence_keys == (
        "series-001-occ-001",
        "series-001-occ-002",
        "series-001-occ-003",
    )
    assert result.verified is True


def test_recurrence_delete_is_idempotent() -> None:
    delete = calendar_recurrence.RecurrenceMutationRequest(
        calendar_recurrence.RecurrenceMutationAction.DELETE,
        series_key="series-001",
    )
    series, result = calendar_recurrence.mutate_recurrence_series(
        (_series(),), delete, readiness=_ready()
    )
    assert series == ()
    assert result.changed is True
    series, result = calendar_recurrence.mutate_recurrence_series(
        series, delete, readiness=_ready()
    )
    assert result.changed is False


def test_recurrence_is_bounded() -> None:
    with pytest.raises(ValueError, match="occurrence_count"):
        calendar_recurrence.SyntheticRecurrenceSeries(
            series_key="series-001",
            anchor_event_key="event-001",
            frequency=calendar_recurrence.RecurrenceFrequency.DAILY,
            interval=1,
            occurrence_count=101,
        )


def test_out084_remains_reserved_and_not_public() -> None:
    outlook = default_application_registry().get(ApplicationKey.OUTLOOK)
    assert outlook.state is ApplicationState.RESERVED
    assert default_tool_registry().by_application("outlook") == ()
