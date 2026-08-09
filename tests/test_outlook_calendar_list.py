from __future__ import annotations

from m365_mcp.apps.outlook import calendar_list, mock_ui, readiness
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


def test_calendar_listing_reports_bounded_counters() -> None:
    fixture = mock_ui.default_outlook_fixture()
    result = calendar_list.list_fixture_calendars(fixture, readiness=_ready_report())

    assert result.synthetic is True
    assert result.calendar_count == 2
    assert result.readable_count == 2
    assert result.default_calendar_key == "cal-primary"
    assert [node.kind for node in result.calendars] == [
        calendar_list.CalendarKind.PRIMARY,
        calendar_list.CalendarKind.GROUP,
    ]


def test_single_calendar_read_returns_projection() -> None:
    fixture = mock_ui.default_outlook_fixture()
    node = calendar_list.read_fixture_calendar(
        fixture,
        "cal-team",
        readiness=_ready_report(),
    )

    assert node.calendar_key == "cal-team"
    assert node.is_default_view is False
    assert node.can_read is True
    assert node.color_token is calendar_list.CalendarColorToken.GREEN
    assert node.to_projection()["kind"] == calendar_list.CalendarKind.GROUP.value


def test_calendar_projection_carries_no_identity_or_browser_primitives() -> None:
    fixture = mock_ui.default_outlook_fixture()
    listing = calendar_list.list_fixture_calendars(fixture, readiness=_ready_report())
    projection = repr([node.to_projection() for node in listing.calendars]).lower()

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


def test_unready_or_non_synthetic_calendar_reads_fail_closed() -> None:
    fixture = mock_ui.default_outlook_fixture()

    for call in (
        lambda: calendar_list.list_fixture_calendars(fixture, readiness=_unready_report()),
        lambda: calendar_list.read_fixture_calendar(
            fixture,
            "cal-primary",
            readiness=_unready_report(),
        ),
    ):
        try:
            call()
        except ValueError as exc:
            assert "read-only discovery is not ready" in str(exc)
        else:
            raise AssertionError("unready calendar read must fail closed")

    live_like = mock_ui.OutlookMockFixture(
        fixture_version=fixture.fixture_version,
        synthetic=False,
        mailbox_key=fixture.mailbox_key,
        folders=fixture.folders,
        messages=fixture.messages,
    )
    try:
        calendar_list.list_fixture_calendars(live_like, readiness=_ready_report())
    except ValueError as exc:
        assert "requires synthetic=true" in str(exc)
    else:
        raise AssertionError("non-synthetic calendar read must fail closed")


def test_invalid_calendar_definitions_fail_closed() -> None:
    invalid = (
        {"calendar_key": "bad key"},
        {"calendar_key": ""},
        {"display_name": " "},
        {"kind": "PRIMARY"},
        {"color_token": "BLUE"},
        {"is_default_view": "yes"},
        {"can_read": "no"},
        {"is_default_view": True, "can_read": False},
    )
    for overrides in invalid:
        values: dict[str, object] = {
            "calendar_key": "cal-x",
            "display_name": "Synthetic X",
        }
        values.update(overrides)
        try:
            calendar_list.SyntheticCalendar(**values)  # type: ignore[arg-type]
        except ValueError:
            pass
        else:
            raise AssertionError(f"invalid calendar definition accepted: {values!r}")


def test_invalid_calendar_catalogs_fail_closed() -> None:
    fixture = mock_ui.default_outlook_fixture()
    primary = calendar_list.SyntheticCalendar(
        calendar_key="cal-primary",
        display_name="Synthetic Calendar",
        kind=calendar_list.CalendarKind.PRIMARY,
        is_default_view=True,
    )
    duplicated = (primary, primary)
    no_primary = (
        calendar_list.SyntheticCalendar(
            calendar_key="cal-a",
            display_name="Synthetic A",
            is_default_view=True,
        ),
    )
    two_defaults = (
        primary,
        calendar_list.SyntheticCalendar(
            calendar_key="cal-b",
            display_name="Synthetic B",
            is_default_view=True,
        ),
    )

    for catalog, expected in (
        ((), "must not be empty"),
        (duplicated, "unique per calendar_key"),
        (no_primary, "exactly one PRIMARY calendar"),
        (two_defaults, "exactly one default-view calendar"),
    ):
        try:
            calendar_list.list_fixture_calendars(
                fixture,
                readiness=_ready_report(),
                calendars=catalog,
            )
        except ValueError as exc:
            assert expected in str(exc)
        else:
            raise AssertionError(f"invalid calendar catalog accepted: {expected}")


def test_unknown_and_malformed_calendar_key_fail_closed() -> None:
    fixture = mock_ui.default_outlook_fixture()

    for calendar_key, expected in (
        ("cal-999", "synthetic calendar_key not found"),
        (" cal-primary", "non-empty semantic token"),
    ):
        try:
            calendar_list.read_fixture_calendar(
                fixture,
                calendar_key,
                readiness=_ready_report(),
            )
        except ValueError as exc:
            assert expected in str(exc)
        else:
            raise AssertionError(f"invalid calendar_key accepted: {calendar_key!r}")


def test_out020_keeps_outlook_activation_absent() -> None:
    assert default_tool_registry().by_application("outlook") == ()
    assert default_capability_registry().by_application("outlook") == ()
