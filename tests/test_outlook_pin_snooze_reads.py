from __future__ import annotations

from m365_mcp.apps.outlook import mock_ui, pin_snooze_reads, readiness
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


def test_pin_snooze_listing_reports_bounded_counters() -> None:
    fixture = mock_ui.default_outlook_fixture()
    result = pin_snooze_reads.list_fixture_pin_snooze_state(fixture, readiness=_ready_report())

    assert result.synthetic is True
    assert len(result.items) == len(fixture.messages)
    assert result.pinned_count == 1
    assert result.snoozed_count == 1
    assert result.hidden_count == 1
    assert result.reference_day_offset == 0


def test_elapsed_snooze_stops_hiding_the_message() -> None:
    fixture = mock_ui.default_outlook_fixture()

    before = pin_snooze_reads.read_fixture_pin_snooze_state(
        fixture,
        "msg-002",
        readiness=_ready_report(),
        reference_day_offset=0,
    )
    assert before.is_snooze_elapsed is False
    assert before.is_hidden_from_default_list is True

    after = pin_snooze_reads.read_fixture_pin_snooze_state(
        fixture,
        "msg-002",
        readiness=_ready_report(),
        reference_day_offset=3,
    )
    assert after.is_snooze_elapsed is True
    assert after.is_hidden_from_default_list is False

    listing = pin_snooze_reads.list_fixture_pin_snooze_state(
        fixture,
        readiness=_ready_report(),
        reference_day_offset=10,
    )
    assert listing.snoozed_count == 1
    assert listing.hidden_count == 0


def test_absent_marker_defaults_to_neither_pinned_nor_snoozed() -> None:
    fixture = mock_ui.default_outlook_fixture()
    state = pin_snooze_reads.read_fixture_pin_snooze_state(
        fixture,
        "msg-001",
        readiness=_ready_report(),
        markers=(),
    )

    assert state.is_pinned is False
    assert state.snooze_state is pin_snooze_reads.SnoozeState.NOT_SNOOZED
    assert state.snooze_until_day_offset is None
    assert state.is_snooze_elapsed is False
    assert state.is_hidden_from_default_list is False


def test_pin_snooze_projection_carries_no_identity_or_browser_primitives() -> None:
    fixture = mock_ui.default_outlook_fixture()
    listing = pin_snooze_reads.list_fixture_pin_snooze_state(fixture, readiness=_ready_report())
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


def test_unready_or_non_synthetic_pin_snooze_reads_fail_closed() -> None:
    fixture = mock_ui.default_outlook_fixture()

    for call in (
        lambda: pin_snooze_reads.list_fixture_pin_snooze_state(
            fixture,
            readiness=_unready_report(),
        ),
        lambda: pin_snooze_reads.read_fixture_pin_snooze_state(
            fixture,
            "msg-001",
            readiness=_unready_report(),
        ),
    ):
        try:
            call()
        except ValueError as exc:
            assert "read-only discovery is not ready" in str(exc)
        else:
            raise AssertionError("unready pin/snooze read must fail closed")

    live_like = mock_ui.OutlookMockFixture(
        fixture_version=fixture.fixture_version,
        synthetic=False,
        mailbox_key=fixture.mailbox_key,
        folders=fixture.folders,
        messages=fixture.messages,
    )
    try:
        pin_snooze_reads.list_fixture_pin_snooze_state(live_like, readiness=_ready_report())
    except ValueError as exc:
        assert "requires synthetic=true" in str(exc)
    else:
        raise AssertionError("non-synthetic pin/snooze read must fail closed")


def test_inconsistent_pin_snooze_markers_fail_closed() -> None:
    invalid = (
        {"snooze_state": pin_snooze_reads.SnoozeState.SNOOZED},
        {"snooze_until_day_offset": 2},
        {
            "snooze_state": pin_snooze_reads.SnoozeState.SNOOZED,
            "snooze_until_day_offset": 99999,
        },
        {
            "is_pinned": True,
            "snooze_state": pin_snooze_reads.SnoozeState.SNOOZED,
            "snooze_until_day_offset": 2,
        },
        {"message_key": "bad key"},
        {"snooze_state": "SNOOZED"},
        {"is_pinned": "yes"},
    )
    for overrides in invalid:
        values: dict[str, object] = {"message_key": "msg-001"}
        values.update(overrides)
        try:
            pin_snooze_reads.PinSnoozeMarker(**values)  # type: ignore[arg-type]
        except ValueError:
            pass
        else:
            raise AssertionError(f"invalid pin/snooze marker accepted: {values!r}")


def test_duplicate_and_dangling_markers_fail_closed() -> None:
    fixture = mock_ui.default_outlook_fixture()
    duplicated = (
        pin_snooze_reads.PinSnoozeMarker(message_key="msg-001", is_pinned=True),
        pin_snooze_reads.PinSnoozeMarker(message_key="msg-001"),
    )
    dangling = (pin_snooze_reads.PinSnoozeMarker(message_key="msg-999", is_pinned=True),)

    for catalog, expected in (
        (duplicated, "unique per message_key"),
        (dangling, "unknown synthetic message_key"),
    ):
        try:
            pin_snooze_reads.list_fixture_pin_snooze_state(
                fixture,
                readiness=_ready_report(),
                markers=catalog,
            )
        except ValueError as exc:
            assert expected in str(exc)
        else:
            raise AssertionError(f"invalid pin/snooze catalog accepted: {expected}")


def test_unknown_message_and_reference_offset_fail_closed() -> None:
    fixture = mock_ui.default_outlook_fixture()

    for message_key, expected in (
        ("msg-999", "synthetic message_key not found"),
        (" msg-001", "non-empty semantic token"),
    ):
        try:
            pin_snooze_reads.read_fixture_pin_snooze_state(
                fixture,
                message_key,
                readiness=_ready_report(),
            )
        except ValueError as exc:
            assert expected in str(exc)
        else:
            raise AssertionError(f"invalid message_key accepted: {message_key!r}")

    try:
        pin_snooze_reads.list_fixture_pin_snooze_state(
            fixture,
            readiness=_ready_report(),
            reference_day_offset=-99999,
        )
    except ValueError as exc:
        assert "bounded day-offset window" in str(exc)
    else:
        raise AssertionError("out-of-range reference offset must fail closed")


def test_out019_keeps_outlook_activation_absent() -> None:
    assert default_tool_registry().by_application("outlook") == ()
    assert default_capability_registry().by_application("outlook") == ()
