from __future__ import annotations

from m365_mcp.apps.outlook import (
    availability_reads,
    calendar_list,
    mock_ui,
    readiness,
    shared_calendar_reads,
)
from m365_mcp.capability_registry import default_capability_registry
from m365_mcp.tool_registry import default_tool_registry


def _ready_report() -> readiness.OutlookReadinessReport:
    return readiness.OutlookReadinessReport(
        state=readiness.OutlookReadinessState.DISCOVERY_READY,
        primary_context_verified=True,
        shared_context_verified=True,
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


def _window() -> availability_reads.AvailabilityWindow:
    return availability_reads.AvailabilityWindow(
        from_day_offset=2,
        to_day_offset=2,
        day_start_minute=540,
        day_end_minute=660,
        slot_minutes=60,
    )


def test_permission_levels_map_to_bounded_read_state() -> None:
    fixture = mock_ui.default_outlook_fixture()

    free_busy = shared_calendar_reads.read_shared_calendar_state(
        fixture,
        "scope-team-freebusy",
        readiness=_ready_report(),
    )
    assert free_busy.may_read_availability is True
    assert free_busy.may_read_events is False
    assert free_busy.may_read_subjects is False

    limited = shared_calendar_reads.read_shared_calendar_state(
        fixture,
        "scope-team-limited",
        readiness=_ready_report(),
    )
    assert limited.may_read_events is True
    assert limited.may_read_subjects is False

    full_scope = (
        shared_calendar_reads.SharedCalendarScope(
            scope_key="scope-full",
            calendar_key="cal-team",
            permission=shared_calendar_reads.SharedCalendarPermission.FULL_DETAILS,
        ),
    )
    full = shared_calendar_reads.read_shared_calendar_state(
        fixture,
        "scope-full",
        readiness=_ready_report(),
        scopes=full_scope,
    )
    assert full.may_read_subjects is True

    none_scope = (
        shared_calendar_reads.SharedCalendarScope(
            scope_key="scope-none",
            calendar_key="cal-team",
            permission=shared_calendar_reads.SharedCalendarPermission.NONE,
        ),
    )
    revoked = shared_calendar_reads.read_shared_calendar_state(
        fixture,
        "scope-none",
        readiness=_ready_report(),
        scopes=none_scope,
    )
    assert revoked.may_read_availability is False


def test_free_busy_scope_reads_availability_but_not_events() -> None:
    fixture = mock_ui.default_outlook_fixture()

    availability = shared_calendar_reads.read_shared_calendar_availability(
        fixture,
        "scope-team-freebusy",
        _window(),
        readiness=_ready_report(),
    )
    assert availability.calendar_key == "cal-team"
    assert availability.slot_count == 2
    assert availability.busy_slot_count == 1

    try:
        shared_calendar_reads.list_shared_calendar_events(
            fixture,
            "scope-team-freebusy",
            readiness=_ready_report(),
        )
    except ValueError as exc:
        assert "does not allow event reads" in str(exc)
    else:
        raise AssertionError("free-busy scope must not read events")


def test_limited_details_scope_redacts_event_subjects() -> None:
    fixture = mock_ui.default_outlook_fixture()
    listing = shared_calendar_reads.list_shared_calendar_events(
        fixture,
        "scope-team-limited",
        readiness=_ready_report(),
    )

    assert [item.event_key for item in listing.items] == ["evt-003"]
    assert all(
        item.subject == "REDACTED_BY_SHARED_CALENDAR_PERMISSION" for item in listing.items
    )
    assert "synthetic team sync" not in repr(
        [item.to_projection() for item in listing.items]
    ).lower()


def test_full_details_scope_preserves_event_subjects() -> None:
    fixture = mock_ui.default_outlook_fixture()
    scopes = (
        shared_calendar_reads.SharedCalendarScope(
            scope_key="scope-full",
            calendar_key="cal-team",
            permission=shared_calendar_reads.SharedCalendarPermission.FULL_DETAILS,
        ),
    )
    listing = shared_calendar_reads.list_shared_calendar_events(
        fixture,
        "scope-full",
        readiness=_ready_report(),
        scopes=scopes,
    )

    assert [item.subject for item in listing.items] == ["Synthetic team sync"]


def test_revoked_scope_blocks_every_read() -> None:
    fixture = mock_ui.default_outlook_fixture()
    scopes = (
        shared_calendar_reads.SharedCalendarScope(
            scope_key="scope-none",
            calendar_key="cal-team",
            permission=shared_calendar_reads.SharedCalendarPermission.NONE,
        ),
    )

    try:
        shared_calendar_reads.read_shared_calendar_availability(
            fixture,
            "scope-none",
            _window(),
            readiness=_ready_report(),
            scopes=scopes,
        )
    except ValueError as exc:
        assert "does not allow availability reads" in str(exc)
    else:
        raise AssertionError("revoked scope must not read availability")

    try:
        shared_calendar_reads.list_shared_calendar_events(
            fixture,
            "scope-none",
            readiness=_ready_report(),
            scopes=scopes,
        )
    except ValueError as exc:
        assert "does not allow event reads" in str(exc)
    else:
        raise AssertionError("revoked scope must not read events")


def test_shared_calendar_projection_carries_no_identity_or_browser_primitives() -> None:
    fixture = mock_ui.default_outlook_fixture()
    state = shared_calendar_reads.read_shared_calendar_state(
        fixture,
        "scope-team-limited",
        readiness=_ready_report(),
    )
    projection = repr(state.to_projection()).lower()

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


def test_unready_or_non_synthetic_shared_calendar_reads_fail_closed() -> None:
    fixture = mock_ui.default_outlook_fixture()

    try:
        shared_calendar_reads.read_shared_calendar_state(
            fixture,
            "scope-team-limited",
            readiness=_unready_report(),
        )
    except ValueError as exc:
        assert "read-only discovery is not ready" in str(exc)
    else:
        raise AssertionError("unready shared calendar read must fail closed")

    live_like = mock_ui.OutlookMockFixture(
        fixture_version=fixture.fixture_version,
        synthetic=False,
        mailbox_key=fixture.mailbox_key,
        folders=fixture.folders,
        messages=fixture.messages,
    )
    try:
        shared_calendar_reads.read_shared_calendar_state(
            live_like,
            "scope-team-limited",
            readiness=_ready_report(),
        )
    except ValueError as exc:
        assert "requires synthetic=true" in str(exc)
    else:
        raise AssertionError("non-synthetic shared calendar read must fail closed")


def test_invalid_shared_scope_definitions_fail_closed() -> None:
    invalid = (
        {"scope_key": "bad key"},
        {"scope_key": ""},
        {"scope_key": "delegate@example.invalid"},
        {"calendar_key": " cal-team"},
        {"permission": "FULL_DETAILS"},
    )
    for overrides in invalid:
        values: dict[str, object] = {
            "scope_key": "scope-x",
            "calendar_key": "cal-team",
        }
        values.update(overrides)
        try:
            shared_calendar_reads.SharedCalendarScope(**values)  # type: ignore[arg-type]
        except ValueError:
            pass
        else:
            raise AssertionError(f"invalid shared scope accepted: {values!r}")


def test_invalid_scope_catalogs_and_unknown_keys_fail_closed() -> None:
    fixture = mock_ui.default_outlook_fixture()
    scope = shared_calendar_reads.SharedCalendarScope(
        scope_key="scope-a",
        calendar_key="cal-team",
    )

    for catalog, expected in (
        ((), "must not be empty"),
        ((scope, scope), "unique per scope_key"),
    ):
        try:
            shared_calendar_reads.read_shared_calendar_state(
                fixture,
                "scope-a",
                readiness=_ready_report(),
                scopes=catalog,
            )
        except ValueError as exc:
            assert expected in str(exc)
        else:
            raise AssertionError(f"invalid scope catalog accepted: {expected}")

    for scope_key, expected in (
        ("scope-999", "synthetic scope_key not found"),
        (" scope-team-limited", "non-empty semantic token"),
    ):
        try:
            shared_calendar_reads.read_shared_calendar_state(
                fixture,
                scope_key,
                readiness=_ready_report(),
            )
        except ValueError as exc:
            assert expected in str(exc)
        else:
            raise AssertionError(f"invalid scope_key accepted: {scope_key!r}")


def test_shared_calendar_inherits_calendar_and_event_gates() -> None:
    fixture = mock_ui.default_outlook_fixture()
    no_primary = (
        calendar_list.SyntheticCalendar(
            calendar_key="cal-primary",
            display_name="Synthetic Calendar",
            is_default_view=True,
        ),
    )

    try:
        shared_calendar_reads.list_shared_calendar_events(
            fixture,
            "scope-team-limited",
            readiness=_ready_report(),
            calendars=no_primary,
        )
    except ValueError as exc:
        assert "exactly one PRIMARY calendar" in str(exc)
    else:
        raise AssertionError("invalid calendar catalog must fail closed")

    dangling = (
        shared_calendar_reads.SharedCalendarScope(
            scope_key="scope-missing",
            calendar_key="cal-missing",
            permission=shared_calendar_reads.SharedCalendarPermission.LIMITED_DETAILS,
        ),
    )
    try:
        shared_calendar_reads.list_shared_calendar_events(
            fixture,
            "scope-missing",
            readiness=_ready_report(),
            scopes=dangling,
        )
    except ValueError as exc:
        assert "unknown synthetic calendar_key" in str(exc)
    else:
        raise AssertionError("unknown shared calendar scope must fail closed")


def test_out024_keeps_outlook_activation_absent() -> None:
    assert default_tool_registry().by_application("outlook") == ()
    assert default_capability_registry().by_application("outlook") == ()
