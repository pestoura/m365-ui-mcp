from __future__ import annotations

from m365_mcp.apps.outlook import calendar_events, calendar_list, mock_ui, readiness
from m365_mcp.capability_registry import default_capability_registry
from m365_mcp.tool_registry import default_tool_registry


def _ready_report() -> readiness.OutlookReadinessReport:
    return readiness.OutlookReadinessReport(
        state=readiness.OutlookReadinessState.DISCOVERY_READY,
        primary_context_verified=True,
        shared_context_verified=False,
        candidate_count=1,
        observed_count=1,
        blocked_count=0,
        reattestation_count=0,
    )


def _unready_report() -> readiness.OutlookReadinessReport:
    return readiness.OutlookReadinessReport(
        state=readiness.OutlookReadinessState.FOUNDATION_READY,
        primary_context_verified=True,
        shared_context_verified=False,
        candidate_count=1,
        observed_count=0,
        blocked_count=0,
        reattestation_count=0,
    )


def test_event_listing_excludes_cancelled_and_orders_deterministically() -> None:
    fixture = mock_ui.default_outlook_fixture()
    result = calendar_events.list_fixture_events(fixture, readiness=_ready_report())

    assert result.synthetic is True
    assert result.has_more is False
    assert [item.event_key for item in result.items] == ["evt-001", "evt-002", "evt-003"]
    assert result.total_matching == 3


def test_cancelled_events_are_opt_in() -> None:
    fixture = mock_ui.default_outlook_fixture()
    result = calendar_events.search_fixture_events(
        fixture,
        calendar_events.EventSearchRequest(include_cancelled=True),
        readiness=_ready_report(),
    )

    assert result.total_matching == 4
    assert any(item.is_cancelled for item in result.items)


def test_event_get_derives_relative_end_position() -> None:
    fixture = mock_ui.default_outlook_fixture()

    timed = calendar_events.get_fixture_event(fixture, "evt-001", readiness=_ready_report())
    assert timed.start_day_offset == 0
    assert timed.end_day_offset == 0
    assert timed.end_minute_of_day == 600

    all_day = calendar_events.get_fixture_event(fixture, "evt-002", readiness=_ready_report())
    assert all_day.is_all_day is True
    assert all_day.end_day_offset == 2
    assert all_day.end_minute_of_day == 0


def test_event_search_filters_and_pagination_are_bounded() -> None:
    fixture = mock_ui.default_outlook_fixture()

    scoped = calendar_events.search_fixture_events(
        fixture,
        calendar_events.EventSearchRequest(calendar_key="cal-team"),
        readiness=_ready_report(),
    )
    assert [item.event_key for item in scoped.items] == ["evt-003"]

    by_query = calendar_events.search_fixture_events(
        fixture,
        calendar_events.EventSearchRequest(query="TEAM SYNC"),
        readiness=_ready_report(),
    )
    assert [item.event_key for item in by_query.items] == ["evt-003"]

    by_show_as = calendar_events.search_fixture_events(
        fixture,
        calendar_events.EventSearchRequest(show_as=calendar_events.EventShowAs.OUT_OF_OFFICE),
        readiness=_ready_report(),
    )
    assert [item.event_key for item in by_show_as.items] == ["evt-002"]

    windowed = calendar_events.search_fixture_events(
        fixture,
        calendar_events.EventSearchRequest(from_day_offset=1, to_day_offset=2),
        readiness=_ready_report(),
    )
    assert [item.event_key for item in windowed.items] == ["evt-002", "evt-003"]

    first_page = calendar_events.search_fixture_events(
        fixture,
        calendar_events.EventSearchRequest(limit=1),
        readiness=_ready_report(),
    )
    assert first_page.has_more is True
    assert first_page.total_matching == 3

    last_page = calendar_events.search_fixture_events(
        fixture,
        calendar_events.EventSearchRequest(offset=2, limit=1),
        readiness=_ready_report(),
    )
    assert last_page.has_more is False


def test_event_projection_carries_no_identity_or_browser_primitives() -> None:
    fixture = mock_ui.default_outlook_fixture()
    listing = calendar_events.list_fixture_events(fixture, readiness=_ready_report())
    projection = repr([item.to_projection() for item in listing.items]).lower()

    for forbidden in (
        "http",
        "://",
        "selector",
        "xpath",
        "javascript",
        "cookie",
        "@",
        "tenant",
        "utc",
    ):
        assert forbidden not in projection


def test_unready_or_non_synthetic_event_reads_fail_closed() -> None:
    fixture = mock_ui.default_outlook_fixture()

    for call in (
        lambda: calendar_events.list_fixture_events(fixture, readiness=_unready_report()),
        lambda: calendar_events.get_fixture_event(
            fixture,
            "evt-001",
            readiness=_unready_report(),
        ),
    ):
        try:
            call()
        except ValueError as exc:
            assert "read-only discovery is not ready" in str(exc)
        else:
            raise AssertionError("unready event read must fail closed")

    live_like = mock_ui.OutlookMockFixture(
        fixture_version=fixture.fixture_version,
        synthetic=False,
        mailbox_key=fixture.mailbox_key,
        folders=fixture.folders,
        messages=fixture.messages,
    )
    try:
        calendar_events.list_fixture_events(live_like, readiness=_ready_report())
    except ValueError as exc:
        assert "requires synthetic=true" in str(exc)
    else:
        raise AssertionError("non-synthetic event read must fail closed")


def test_invalid_event_definitions_fail_closed() -> None:
    invalid = (
        {"event_key": "bad key"},
        {"calendar_key": ""},
        {"subject": " "},
        {"start_day_offset": 99999},
        {"start_minute_of_day": 1440},
        {"start_minute_of_day": -1},
        {"duration_minutes": 0},
        {"duration_minutes": 10**9},
        {"is_all_day": True, "start_minute_of_day": 30},
        {"is_all_day": True, "duration_minutes": 100},
        {"is_cancelled": "yes"},
        {"show_as": "BUSY"},
        {"sensitivity": "NORMAL"},
    )
    for overrides in invalid:
        values: dict[str, object] = {
            "event_key": "evt-x",
            "calendar_key": "cal-primary",
            "subject": "Synthetic X",
            "start_day_offset": 0,
            "start_minute_of_day": 0,
            "duration_minutes": 60,
        }
        values.update(overrides)
        try:
            calendar_events.SyntheticEvent(**values)  # type: ignore[arg-type]
        except ValueError:
            pass
        else:
            raise AssertionError(f"invalid event definition accepted: {values!r}")


def test_invalid_event_search_requests_fail_closed() -> None:
    invalid = (
        {"query": "  "},
        {"query": "x" * 201},
        {"calendar_key": "bad key"},
        {"from_day_offset": 5, "to_day_offset": 1},
        {"from_day_offset": 99999},
        {"offset": -1},
        {"limit": 0},
        {"limit": 101},
        {"include_cancelled": "yes"},
    )
    for overrides in invalid:
        try:
            calendar_events.EventSearchRequest(**overrides)  # type: ignore[arg-type]
        except ValueError:
            pass
        else:
            raise AssertionError(f"invalid event search request accepted: {overrides!r}")


def test_invalid_event_catalog_and_unknown_keys_fail_closed() -> None:
    fixture = mock_ui.default_outlook_fixture()
    base = calendar_events.SyntheticEvent(
        event_key="evt-a",
        calendar_key="cal-primary",
        subject="Synthetic A",
        start_day_offset=0,
        start_minute_of_day=0,
        duration_minutes=60,
    )
    dangling = (
        calendar_events.SyntheticEvent(
            event_key="evt-b",
            calendar_key="cal-missing",
            subject="Synthetic B",
            start_day_offset=0,
            start_minute_of_day=0,
            duration_minutes=60,
        ),
    )

    for catalog, expected in (
        ((base, base), "unique per event_key"),
        (dangling, "unknown synthetic calendar_key"),
    ):
        try:
            calendar_events.list_fixture_events(
                fixture,
                readiness=_ready_report(),
                events=catalog,
            )
        except ValueError as exc:
            assert expected in str(exc)
        else:
            raise AssertionError(f"invalid event catalog accepted: {expected}")

    try:
        calendar_events.list_fixture_events(
            fixture,
            readiness=_ready_report(),
            calendar_key="cal-missing",
        )
    except ValueError as exc:
        assert "unknown synthetic calendar_key" in str(exc)
    else:
        raise AssertionError("unknown calendar scope must fail closed")

    for event_key, expected in (
        ("evt-999", "synthetic event_key not found"),
        (" evt-001", "non-empty semantic token"),
    ):
        try:
            calendar_events.get_fixture_event(
                fixture,
                event_key,
                readiness=_ready_report(),
            )
        except ValueError as exc:
            assert expected in str(exc)
        else:
            raise AssertionError(f"invalid event_key accepted: {event_key!r}")


def test_event_reads_inherit_the_out020_calendar_gate() -> None:
    fixture = mock_ui.default_outlook_fixture()
    no_primary = (
        calendar_list.SyntheticCalendar(
            calendar_key="cal-primary",
            display_name="Synthetic Calendar",
            is_default_view=True,
        ),
    )

    try:
        calendar_events.list_fixture_events(
            fixture,
            readiness=_ready_report(),
            calendars=no_primary,
        )
    except ValueError as exc:
        assert "exactly one PRIMARY calendar" in str(exc)
    else:
        raise AssertionError("invalid calendar catalog must fail closed for event reads")


def test_out021_keeps_outlook_activation_absent() -> None:
    assert default_tool_registry().by_application("outlook") == ()
    assert default_capability_registry().by_application("outlook") == ()
