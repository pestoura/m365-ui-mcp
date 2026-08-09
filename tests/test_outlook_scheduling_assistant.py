from __future__ import annotations

from m365_mcp.apps.outlook import (
    availability_reads,
    calendar_list,
    mock_ui,
    readiness,
    scheduling_assistant,
)
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


def _window() -> availability_reads.AvailabilityWindow:
    return availability_reads.AvailabilityWindow(
        from_day_offset=0,
        to_day_offset=0,
        day_start_minute=480,
        day_end_minute=660,
        slot_minutes=60,
    )


def test_scheduling_grid_composes_one_row_per_participant() -> None:
    fixture = mock_ui.default_outlook_fixture()
    grid = scheduling_assistant.read_fixture_scheduling_grid(
        fixture,
        _window(),
        readiness=_ready_report(),
    )

    assert grid.synthetic is True
    assert grid.participant_count == 2
    assert grid.slot_count == 3
    assert [row.participant_key for row in grid.rows] == [
        "participant-organizer",
        "participant-required",
    ]
    assert all(len(row.states) == grid.slot_count for row in grid.rows)


def test_organizer_conflict_marks_the_slot_conflicted() -> None:
    fixture = mock_ui.default_outlook_fixture()
    grid = scheduling_assistant.read_fixture_scheduling_grid(
        fixture,
        _window(),
        readiness=_ready_report(),
    )

    assert [slot.feasibility.value for slot in grid.slots] == [
        "ALL_FREE",
        "CONFLICTED",
        "ALL_FREE",
    ]
    assert grid.all_free_slot_count == 2
    assert grid.required_free_slot_count == 2
    assert grid.slots[1].conflicted_participant_count == 1
    assert grid.slots[1].free_participant_count == 1


def test_optional_participant_conflict_still_allows_required_free() -> None:
    fixture = mock_ui.default_outlook_fixture()
    participants = (
        scheduling_assistant.SyntheticParticipant(
            participant_key="participant-organizer",
            role=scheduling_assistant.ParticipantRole.ORGANIZER,
            calendar_key="cal-team",
        ),
        scheduling_assistant.SyntheticParticipant(
            participant_key="participant-optional",
            role=scheduling_assistant.ParticipantRole.OPTIONAL,
            calendar_key="cal-primary",
        ),
    )
    grid = scheduling_assistant.read_fixture_scheduling_grid(
        fixture,
        _window(),
        readiness=_ready_report(),
        participants=participants,
    )

    assert [slot.feasibility.value for slot in grid.slots] == [
        "ALL_FREE",
        "REQUIRED_FREE",
        "ALL_FREE",
    ]
    assert grid.all_free_slot_count == 2
    assert grid.required_free_slot_count == 3


def test_scheduling_projection_carries_no_identity_or_browser_primitives() -> None:
    fixture = mock_ui.default_outlook_fixture()
    grid = scheduling_assistant.read_fixture_scheduling_grid(
        fixture,
        _window(),
        readiness=_ready_report(),
    )
    projection = repr(
        [row.to_projection() for row in grid.rows]
        + [slot.to_projection() for slot in grid.slots]
    ).lower()

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

    assert "subject" not in projection
    assert "synthetic planning session" not in projection


def test_unready_or_non_synthetic_scheduling_reads_fail_closed() -> None:
    fixture = mock_ui.default_outlook_fixture()

    try:
        scheduling_assistant.read_fixture_scheduling_grid(
            fixture,
            _window(),
            readiness=_unready_report(),
        )
    except ValueError as exc:
        assert "read-only discovery is not ready" in str(exc)
    else:
        raise AssertionError("unready scheduling read must fail closed")

    live_like = mock_ui.OutlookMockFixture(
        fixture_version=fixture.fixture_version,
        synthetic=False,
        mailbox_key=fixture.mailbox_key,
        folders=fixture.folders,
        messages=fixture.messages,
    )
    try:
        scheduling_assistant.read_fixture_scheduling_grid(
            live_like,
            _window(),
            readiness=_ready_report(),
        )
    except ValueError as exc:
        assert "requires synthetic=true" in str(exc)
    else:
        raise AssertionError("non-synthetic scheduling read must fail closed")


def test_invalid_participant_definitions_fail_closed() -> None:
    invalid = (
        {"participant_key": "bad key"},
        {"participant_key": ""},
        {"participant_key": "person@example.invalid"},
        {"calendar_key": " cal-primary"},
        {"role": "REQUIRED"},
    )
    for overrides in invalid:
        values: dict[str, object] = {"participant_key": "participant-x"}
        values.update(overrides)
        try:
            scheduling_assistant.SyntheticParticipant(**values)  # type: ignore[arg-type]
        except ValueError:
            pass
        else:
            raise AssertionError(f"invalid participant accepted: {values!r}")


def test_invalid_participant_catalogs_fail_closed() -> None:
    fixture = mock_ui.default_outlook_fixture()
    organizer = scheduling_assistant.SyntheticParticipant(
        participant_key="participant-organizer",
        role=scheduling_assistant.ParticipantRole.ORGANIZER,
        calendar_key="cal-primary",
    )
    no_organizer = (
        scheduling_assistant.SyntheticParticipant(
            participant_key="participant-a",
            calendar_key="cal-primary",
        ),
    )
    two_organizers = (
        organizer,
        scheduling_assistant.SyntheticParticipant(
            participant_key="participant-b",
            role=scheduling_assistant.ParticipantRole.ORGANIZER,
            calendar_key="cal-team",
        ),
    )

    for catalog, expected in (
        ((), "must not be empty"),
        ((organizer, organizer), "unique per participant_key"),
        (no_organizer, "exactly one ORGANIZER"),
        (two_organizers, "exactly one ORGANIZER"),
    ):
        try:
            scheduling_assistant.read_fixture_scheduling_grid(
                fixture,
                _window(),
                readiness=_ready_report(),
                participants=catalog,
            )
        except ValueError as exc:
            assert expected in str(exc)
        else:
            raise AssertionError(f"invalid participant catalog accepted: {expected}")


def test_scheduling_requires_a_bounded_window_object() -> None:
    fixture = mock_ui.default_outlook_fixture()
    try:
        scheduling_assistant.read_fixture_scheduling_grid(
            fixture,
            "0..1",  # type: ignore[arg-type]
            readiness=_ready_report(),
        )
    except ValueError as exc:
        assert "bounded AvailabilityWindow" in str(exc)
    else:
        raise AssertionError("free-form window input must fail closed")


def test_scheduling_inherits_calendar_and_availability_gates() -> None:
    fixture = mock_ui.default_outlook_fixture()
    no_primary = (
        calendar_list.SyntheticCalendar(
            calendar_key="cal-primary",
            display_name="Synthetic Calendar",
            is_default_view=True,
        ),
    )

    try:
        scheduling_assistant.read_fixture_scheduling_grid(
            fixture,
            _window(),
            readiness=_ready_report(),
            calendars=no_primary,
        )
    except ValueError as exc:
        assert "exactly one PRIMARY calendar" in str(exc)
    else:
        raise AssertionError("invalid calendar catalog must fail closed")

    dangling = (
        scheduling_assistant.SyntheticParticipant(
            participant_key="participant-organizer",
            role=scheduling_assistant.ParticipantRole.ORGANIZER,
            calendar_key="cal-missing",
        ),
    )
    try:
        scheduling_assistant.read_fixture_scheduling_grid(
            fixture,
            _window(),
            readiness=_ready_report(),
            participants=dangling,
        )
    except ValueError as exc:
        assert "unknown synthetic calendar_key" in str(exc)
    else:
        raise AssertionError("unknown participant calendar scope must fail closed")


def test_out023_keeps_outlook_activation_absent() -> None:
    assert default_tool_registry().by_application("outlook") == ()
    assert default_capability_registry().by_application("outlook") == ()
