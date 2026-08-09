from __future__ import annotations

from m365_mcp.apps.outlook import availability_reads, calendar_list, mock_ui, readiness
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


def test_availability_marks_the_overlapping_event_window_busy() -> None:
    fixture = mock_ui.default_outlook_fixture()
    window = availability_reads.AvailabilityWindow(
        from_day_offset=0,
        to_day_offset=0,
        day_start_minute=480,
        day_end_minute=660,
        slot_minutes=60,
    )
    result = availability_reads.read_fixture_availability(
        fixture,
        window,
        readiness=_ready_report(),
    )

    assert result.synthetic is True
    assert result.slot_count == 3
    assert [slot.state.value for slot in result.slots] == ["FREE", "BUSY", "FREE"]
    assert result.free_slot_count == 2
    assert result.busy_slot_count == 1
    assert result.slots[1].overlapping_event_count == 1


def test_all_day_event_blocks_the_whole_day_as_out_of_office() -> None:
    fixture = mock_ui.default_outlook_fixture()
    window = availability_reads.AvailabilityWindow(
        from_day_offset=1,
        to_day_offset=1,
        slot_minutes=360,
    )
    result = availability_reads.read_fixture_availability(
        fixture,
        window,
        readiness=_ready_report(),
    )

    assert result.slot_count == 4
    assert {slot.state for slot in result.slots} == {
        availability_reads.AvailabilityState.OUT_OF_OFFICE
    }
    assert result.free_slot_count == 0


def test_calendar_scope_and_multi_day_window_are_respected() -> None:
    fixture = mock_ui.default_outlook_fixture()
    window = availability_reads.AvailabilityWindow(
        from_day_offset=0,
        to_day_offset=2,
        day_start_minute=540,
        day_end_minute=660,
        slot_minutes=60,
    )

    team_only = availability_reads.read_fixture_availability(
        fixture,
        window,
        readiness=_ready_report(),
        calendar_key="cal-team",
    )
    assert team_only.calendar_key == "cal-team"
    assert team_only.slot_count == 6
    assert [slot.day_offset for slot in team_only.slots] == [0, 0, 1, 1, 2, 2]
    assert team_only.busy_slot_count == 1
    assert team_only.slots[4].state is availability_reads.AvailabilityState.FREE
    assert team_only.slots[5].state is availability_reads.AvailabilityState.TENTATIVE
    assert team_only.slots[5].overlapping_event_count == 1

    everything = availability_reads.read_fixture_availability(
        fixture,
        window,
        readiness=_ready_report(),
    )
    assert everything.busy_slot_count > team_only.busy_slot_count


def test_cancelled_event_does_not_block_availability() -> None:
    fixture = mock_ui.default_outlook_fixture()
    window = availability_reads.AvailabilityWindow(
        from_day_offset=3,
        to_day_offset=3,
        day_start_minute=660,
        day_end_minute=720,
        slot_minutes=60,
    )
    result = availability_reads.read_fixture_availability(
        fixture,
        window,
        readiness=_ready_report(),
    )

    assert result.slot_count == 1
    assert result.slots[0].state is availability_reads.AvailabilityState.FREE
    assert result.slots[0].overlapping_event_count == 0


def test_availability_projection_carries_no_identity_or_browser_primitives() -> None:
    fixture = mock_ui.default_outlook_fixture()
    window = availability_reads.AvailabilityWindow(from_day_offset=0, to_day_offset=0)
    result = availability_reads.read_fixture_availability(
        fixture,
        window,
        readiness=_ready_report(),
    )
    projection = repr([slot.to_projection() for slot in result.slots]).lower()

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


def test_unready_or_non_synthetic_availability_reads_fail_closed() -> None:
    fixture = mock_ui.default_outlook_fixture()
    window = availability_reads.AvailabilityWindow(from_day_offset=0, to_day_offset=0)

    try:
        availability_reads.read_fixture_availability(
            fixture,
            window,
            readiness=_unready_report(),
        )
    except ValueError as exc:
        assert "read-only discovery is not ready" in str(exc)
    else:
        raise AssertionError("unready availability read must fail closed")

    live_like = mock_ui.OutlookMockFixture(
        fixture_version=fixture.fixture_version,
        synthetic=False,
        mailbox_key=fixture.mailbox_key,
        folders=fixture.folders,
        messages=fixture.messages,
    )
    try:
        availability_reads.read_fixture_availability(
            live_like,
            window,
            readiness=_ready_report(),
        )
    except ValueError as exc:
        assert "requires synthetic=true" in str(exc)
    else:
        raise AssertionError("non-synthetic availability read must fail closed")


def test_invalid_availability_windows_fail_closed() -> None:
    invalid = (
        {"from_day_offset": 5, "to_day_offset": 1},
        {"from_day_offset": 0, "to_day_offset": 99999},
        {"from_day_offset": 0, "to_day_offset": 60},
        {"day_start_minute": 1440},
        {"day_start_minute": -1},
        {"day_end_minute": 0},
        {"day_end_minute": 1441},
        {"day_start_minute": 600, "day_end_minute": 600},
        {"slot_minutes": 1},
        {"slot_minutes": 100000},
        {"day_start_minute": 0, "day_end_minute": 100, "slot_minutes": 30},
        {"slot_minutes": "30"},
    )
    for overrides in invalid:
        values: dict[str, object] = {"from_day_offset": 0, "to_day_offset": 0}
        values.update(overrides)
        try:
            availability_reads.AvailabilityWindow(**values)  # type: ignore[arg-type]
        except ValueError:
            pass
        else:
            raise AssertionError(f"invalid availability window accepted: {values!r}")


def test_availability_requires_a_bounded_window_object() -> None:
    fixture = mock_ui.default_outlook_fixture()
    try:
        availability_reads.read_fixture_availability(
            fixture,
            "0..1",  # type: ignore[arg-type]
            readiness=_ready_report(),
        )
    except ValueError as exc:
        assert "bounded AvailabilityWindow" in str(exc)
    else:
        raise AssertionError("free-form window input must fail closed")


def test_availability_inherits_calendar_and_event_gates() -> None:
    fixture = mock_ui.default_outlook_fixture()
    window = availability_reads.AvailabilityWindow(from_day_offset=0, to_day_offset=0)
    no_primary = (
        calendar_list.SyntheticCalendar(
            calendar_key="cal-primary",
            display_name="Synthetic Calendar",
            is_default_view=True,
        ),
    )

    try:
        availability_reads.read_fixture_availability(
            fixture,
            window,
            readiness=_ready_report(),
            calendars=no_primary,
        )
    except ValueError as exc:
        assert "exactly one PRIMARY calendar" in str(exc)
    else:
        raise AssertionError("invalid calendar catalog must fail closed")

    try:
        availability_reads.read_fixture_availability(
            fixture,
            window,
            readiness=_ready_report(),
            calendar_key="cal-missing",
        )
    except ValueError as exc:
        assert "unknown synthetic calendar_key" in str(exc)
    else:
        raise AssertionError("unknown calendar scope must fail closed")


def test_out022_keeps_outlook_activation_absent() -> None:
    assert default_tool_registry().by_application("outlook") == ()
    assert default_capability_registry().by_application("outlook") == ()
