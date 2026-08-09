from __future__ import annotations

from m365_mcp.apps.outlook import category_reads, mock_ui, readiness
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


def test_category_listing_projects_bounded_usage_counts() -> None:
    fixture = mock_ui.default_outlook_fixture()
    result = category_reads.list_fixture_categories(fixture, readiness=_ready_report())

    assert result.synthetic is True
    assert result.category_count == 2
    assert result.assigned_message_count == 2
    by_key = {item.category_key: item for item in result.categories}
    assert by_key["cat-project"].assigned_message_count == 1
    assert by_key["cat-followup"].assigned_message_count == 1
    assert by_key["cat-project"].color_token is category_reads.CategoryColorToken.BLUE


def test_message_category_state_is_deterministic_and_sorted() -> None:
    fixture = mock_ui.default_outlook_fixture()
    assignments = (
        category_reads.CategoryAssignment(message_key="msg-001", category_key="cat-followup"),
        category_reads.CategoryAssignment(message_key="msg-001", category_key="cat-project"),
    )
    state = category_reads.read_fixture_message_categories(
        fixture,
        "msg-001",
        readiness=_ready_report(),
        assignments=assignments,
    )

    assert state.category_keys == ("cat-followup", "cat-project")
    assert state.category_count == 2

    empty = category_reads.read_fixture_message_categories(
        fixture,
        "msg-002",
        readiness=_ready_report(),
        assignments=assignments,
    )
    assert empty.category_keys == ()
    assert empty.category_count == 0


def test_category_projection_carries_no_identity_or_browser_primitives() -> None:
    fixture = mock_ui.default_outlook_fixture()
    listing = category_reads.list_fixture_categories(fixture, readiness=_ready_report())
    state = category_reads.read_fixture_message_categories(
        fixture,
        "msg-001",
        readiness=_ready_report(),
    )
    projection = repr(
        [item.to_projection() for item in listing.categories] + [state.to_projection()]
    ).lower()

    for forbidden in (
        "http",
        "://",
        "css=",
        "xpath",
        "selector",
        "javascript",
        "cookie",
        "token=",
        "@",
        "tenant",
    ):
        assert forbidden not in projection


def test_unready_or_non_synthetic_category_reads_fail_closed() -> None:
    fixture = mock_ui.default_outlook_fixture()

    for call in (
        lambda: category_reads.list_fixture_categories(fixture, readiness=_unready_report()),
        lambda: category_reads.read_fixture_message_categories(
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
            raise AssertionError("unready category read must fail closed")

    live_like = mock_ui.OutlookMockFixture(
        fixture_version=fixture.fixture_version,
        synthetic=False,
        mailbox_key=fixture.mailbox_key,
        folders=fixture.folders,
        messages=fixture.messages,
    )
    try:
        category_reads.list_fixture_categories(live_like, readiness=_ready_report())
    except ValueError as exc:
        assert "requires synthetic=true" in str(exc)
    else:
        raise AssertionError("non-synthetic category read must fail closed")


def test_invalid_category_catalogs_and_assignments_fail_closed() -> None:
    fixture = mock_ui.default_outlook_fixture()
    base = category_reads.default_synthetic_categories()

    duplicated = base + (
        category_reads.SyntheticCategory(
            category_key="cat-project",
            display_name="Duplicate",
        ),
    )
    unknown_category = (
        category_reads.CategoryAssignment(message_key="msg-001", category_key="cat-missing"),
    )
    unknown_message = (
        category_reads.CategoryAssignment(message_key="msg-999", category_key="cat-project"),
    )
    duplicate_pair = (
        category_reads.CategoryAssignment(message_key="msg-001", category_key="cat-project"),
        category_reads.CategoryAssignment(message_key="msg-001", category_key="cat-project"),
    )

    cases = (
        (duplicated, None, "keys must be unique"),
        (None, unknown_category, "unknown category_key"),
        (None, unknown_message, "unknown synthetic message_key"),
        (None, duplicate_pair, "assignments must be unique"),
    )
    for categories, assignments, expected in cases:
        try:
            category_reads.list_fixture_categories(
                fixture,
                readiness=_ready_report(),
                categories=categories,
                assignments=assignments,
            )
        except ValueError as exc:
            assert expected in str(exc)
        else:
            raise AssertionError(f"invalid category input accepted: {expected}")


def test_category_token_validation_is_bounded() -> None:
    invalid_categories = (
        {"category_key": "bad key"},
        {"category_key": ""},
        {"display_name": " "},
        {"color_token": "BLUE"},
    )
    for overrides in invalid_categories:
        values: dict[str, object] = {
            "category_key": "cat-x",
            "display_name": "Synthetic",
            "color_token": category_reads.CategoryColorToken.NEUTRAL,
        }
        values.update(overrides)
        try:
            category_reads.SyntheticCategory(**values)  # type: ignore[arg-type]
        except ValueError:
            pass
        else:
            raise AssertionError(f"invalid category accepted: {values!r}")

    for overrides in ({"message_key": "bad key"}, {"category_key": " cat-x"}):
        pair: dict[str, object] = {"message_key": "msg-001", "category_key": "cat-x"}
        pair.update(overrides)
        try:
            category_reads.CategoryAssignment(**pair)  # type: ignore[arg-type]
        except ValueError:
            pass
        else:
            raise AssertionError(f"invalid assignment accepted: {pair!r}")


def test_unknown_message_category_read_fails_closed() -> None:
    fixture = mock_ui.default_outlook_fixture()
    for message_key, expected in (
        ("msg-999", "synthetic message_key not found"),
        (" msg-001", "non-empty semantic token"),
        ("", "non-empty semantic token"),
    ):
        try:
            category_reads.read_fixture_message_categories(
                fixture,
                message_key,
                readiness=_ready_report(),
            )
        except ValueError as exc:
            assert expected in str(exc)
        else:
            raise AssertionError(f"invalid message_key accepted: {message_key!r}")


def test_out017_keeps_outlook_activation_absent() -> None:
    assert default_tool_registry().by_application("outlook") == ()
    assert default_capability_registry().by_application("outlook") == ()
