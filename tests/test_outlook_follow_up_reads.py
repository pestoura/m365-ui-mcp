from __future__ import annotations

from m365_mcp.apps.outlook import follow_up_reads, mock_ui, readiness
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


def test_follow_up_listing_reports_bounded_counters() -> None:
    fixture = mock_ui.default_outlook_fixture()
    result = follow_up_reads.list_fixture_follow_up_state(fixture, readiness=_ready_report())

    assert result.synthetic is True
    assert len(result.items) == len(fixture.messages)
    assert result.flagged_count == 1
    assert result.completed_count == 1
    assert result.overdue_count == 0

    overdue = follow_up_reads.list_fixture_follow_up_state(
        fixture,
        readiness=_ready_report(),
        reference_day_offset=10,
    )
    assert overdue.overdue_count == 1


def test_message_follow_up_state_defaults_to_not_flagged() -> None:
    fixture = mock_ui.default_outlook_fixture()

    flagged = follow_up_reads.read_fixture_follow_up_state(
        fixture,
        "msg-001",
        readiness=_ready_report(),
    )
    assert flagged.state is follow_up_reads.FollowUpState.FLAGGED
    assert flagged.is_flagged is True
    assert flagged.is_completed is False
    assert flagged.due_day_offset == 2

    completed = follow_up_reads.read_fixture_follow_up_state(
        fixture,
        "msg-002",
        readiness=_ready_report(),
    )
    assert completed.is_completed is True
    assert completed.completed_day_offset == -1

    unflagged = follow_up_reads.read_fixture_follow_up_state(
        fixture,
        "msg-001",
        readiness=_ready_report(),
        flags=(),
    )
    assert unflagged.state is follow_up_reads.FollowUpState.NOT_FLAGGED
    assert unflagged.start_day_offset is None
    assert unflagged.due_day_offset is None
    assert unflagged.completed_day_offset is None


def test_follow_up_projection_uses_relative_offsets_and_no_identity() -> None:
    fixture = mock_ui.default_outlook_fixture()
    listing = follow_up_reads.list_fixture_follow_up_state(fixture, readiness=_ready_report())
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
        "t00:",
        "z\"",
    ):
        assert forbidden not in projection


def test_unready_or_non_synthetic_follow_up_reads_fail_closed() -> None:
    fixture = mock_ui.default_outlook_fixture()

    for call in (
        lambda: follow_up_reads.list_fixture_follow_up_state(
            fixture,
            readiness=_unready_report(),
        ),
        lambda: follow_up_reads.read_fixture_follow_up_state(
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
            raise AssertionError("unready follow-up read must fail closed")

    live_like = mock_ui.OutlookMockFixture(
        fixture_version=fixture.fixture_version,
        synthetic=False,
        mailbox_key=fixture.mailbox_key,
        folders=fixture.folders,
        messages=fixture.messages,
    )
    try:
        follow_up_reads.list_fixture_follow_up_state(live_like, readiness=_ready_report())
    except ValueError as exc:
        assert "requires synthetic=true" in str(exc)
    else:
        raise AssertionError("non-synthetic follow-up read must fail closed")


def test_inconsistent_follow_up_flags_fail_closed() -> None:
    invalid = (
        {
            "state": follow_up_reads.FollowUpState.NOT_FLAGGED,
            "due_day_offset": 3,
        },
        {"state": follow_up_reads.FollowUpState.COMPLETED},
        {
            "state": follow_up_reads.FollowUpState.FLAGGED,
            "completed_day_offset": 1,
        },
        {
            "state": follow_up_reads.FollowUpState.FLAGGED,
            "start_day_offset": 5,
            "due_day_offset": 1,
        },
        {
            "state": follow_up_reads.FollowUpState.FLAGGED,
            "due_day_offset": 99999,
        },
        {"message_key": "bad key", "state": follow_up_reads.FollowUpState.FLAGGED},
        {"state": "FLAGGED"},
    )
    for overrides in invalid:
        values: dict[str, object] = {
            "message_key": "msg-001",
            "state": follow_up_reads.FollowUpState.FLAGGED,
        }
        values.update(overrides)
        try:
            follow_up_reads.FollowUpFlag(**values)  # type: ignore[arg-type]
        except ValueError:
            pass
        else:
            raise AssertionError(f"invalid follow-up flag accepted: {values!r}")


def test_duplicate_and_dangling_follow_up_flags_fail_closed() -> None:
    fixture = mock_ui.default_outlook_fixture()
    duplicated = (
        follow_up_reads.FollowUpFlag(
            message_key="msg-001",
            state=follow_up_reads.FollowUpState.FLAGGED,
        ),
        follow_up_reads.FollowUpFlag(
            message_key="msg-001",
            state=follow_up_reads.FollowUpState.FLAGGED,
        ),
    )
    dangling = (
        follow_up_reads.FollowUpFlag(
            message_key="msg-999",
            state=follow_up_reads.FollowUpState.FLAGGED,
        ),
    )

    for catalog, expected in (
        (duplicated, "unique per message_key"),
        (dangling, "unknown synthetic message_key"),
    ):
        try:
            follow_up_reads.list_fixture_follow_up_state(
                fixture,
                readiness=_ready_report(),
                flags=catalog,
            )
        except ValueError as exc:
            assert expected in str(exc)
        else:
            raise AssertionError(f"invalid follow-up catalog accepted: {expected}")


def test_unknown_message_and_reference_offset_fail_closed() -> None:
    fixture = mock_ui.default_outlook_fixture()

    for message_key, expected in (
        ("msg-999", "synthetic message_key not found"),
        (" msg-001", "non-empty semantic token"),
    ):
        try:
            follow_up_reads.read_fixture_follow_up_state(
                fixture,
                message_key,
                readiness=_ready_report(),
            )
        except ValueError as exc:
            assert expected in str(exc)
        else:
            raise AssertionError(f"invalid message_key accepted: {message_key!r}")

    try:
        follow_up_reads.list_fixture_follow_up_state(
            fixture,
            readiness=_ready_report(),
            reference_day_offset=99999,
        )
    except ValueError as exc:
        assert "bounded day-offset window" in str(exc)
    else:
        raise AssertionError("out-of-range reference offset must fail closed")


def test_out018_keeps_outlook_activation_absent() -> None:
    assert default_tool_registry().by_application("outlook") == ()
    assert default_capability_registry().by_application("outlook") == ()
