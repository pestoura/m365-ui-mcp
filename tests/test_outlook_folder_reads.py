from __future__ import annotations

from m365_mcp.apps.outlook import folder_reads, mock_ui, readiness
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


def test_folder_listing_projects_bounded_counts_from_the_synthetic_fixture() -> None:
    fixture = mock_ui.default_outlook_fixture()
    result = folder_reads.list_fixture_folders(fixture, readiness=_ready_report())

    assert result.synthetic is True
    assert result.folder_count == 3
    assert result.max_depth == 0
    by_key = {node.folder_key: node for node in result.folders}
    assert set(by_key) == {"inbox", "archive", "sent"}
    assert by_key["inbox"].message_count == 1
    assert by_key["inbox"].unread_count == 1
    assert by_key["archive"].message_count == 1
    assert by_key["archive"].unread_count == 0
    assert by_key["sent"].message_count == 0
    assert by_key["sent"].unread_count == 0


def test_folder_navigation_resolves_ancestors_and_children_semantically() -> None:
    fixture = mock_ui.default_outlook_fixture()
    nested = (
        folder_reads.SyntheticFolder(folder_key="inbox", display_name="Inbox"),
        folder_reads.SyntheticFolder(
            folder_key="archive",
            display_name="Archive",
            parent_key="inbox",
        ),
        folder_reads.SyntheticFolder(
            folder_key="sent",
            display_name="Sent",
            parent_key="archive",
        ),
    )

    deepest = folder_reads.navigate_fixture_folder(
        fixture,
        "sent",
        readiness=_ready_report(),
        folders=nested,
    )
    assert deepest.ancestor_keys == ("archive", "inbox")
    assert deepest.child_keys == ()
    assert deepest.folder.depth == 2

    middle = folder_reads.navigate_fixture_folder(
        fixture,
        "archive",
        readiness=_ready_report(),
        folders=nested,
    )
    assert middle.ancestor_keys == ("inbox",)
    assert middle.child_keys == ("sent",)
    assert middle.folder.child_count == 1


def test_folder_projection_carries_no_navigation_or_identity_primitives() -> None:
    fixture = mock_ui.default_outlook_fixture()
    navigation = folder_reads.navigate_fixture_folder(
        fixture,
        "inbox",
        readiness=_ready_report(),
    )
    projection = repr(navigation.to_projection()).lower()

    for forbidden in (
        "http",
        "://",
        "css=",
        "xpath",
        "selector",
        "javascript",
        "cookie",
        "token",
        "@",
        "tenant",
        "click",
        "goto",
    ):
        assert forbidden not in projection


def test_unready_or_non_synthetic_folder_reads_fail_closed() -> None:
    fixture = mock_ui.default_outlook_fixture()

    try:
        folder_reads.list_fixture_folders(fixture, readiness=_unready_report())
    except ValueError as exc:
        assert "read-only discovery is not ready" in str(exc)
    else:
        raise AssertionError("unready folder listing must fail closed")

    live_like = mock_ui.OutlookMockFixture(
        fixture_version=fixture.fixture_version,
        synthetic=False,
        mailbox_key=fixture.mailbox_key,
        folders=fixture.folders,
        messages=fixture.messages,
    )
    try:
        folder_reads.list_fixture_folders(live_like, readiness=_ready_report())
    except ValueError as exc:
        assert "requires synthetic=true" in str(exc)
    else:
        raise AssertionError("non-synthetic folder listing must fail closed")


def test_invalid_folder_catalogs_fail_closed() -> None:
    fixture = mock_ui.default_outlook_fixture()
    base = folder_reads.default_synthetic_folders()

    duplicated = base + (
        folder_reads.SyntheticFolder(folder_key="inbox", display_name="Inbox Copy"),
    )
    divergent = (folder_reads.SyntheticFolder(folder_key="inbox", display_name="Inbox"),)
    unknown_parent = (
        folder_reads.SyntheticFolder(folder_key="inbox", display_name="Inbox"),
        folder_reads.SyntheticFolder(folder_key="archive", display_name="Archive"),
        folder_reads.SyntheticFolder(
            folder_key="sent",
            display_name="Sent",
            parent_key="not-a-folder",
        ),
    )

    for catalog, expected in (
        (duplicated, "keys must be unique"),
        (divergent, "does not match synthetic fixture folders"),
        (unknown_parent, "unknown parent_key"),
        ((), "must not be empty"),
    ):
        try:
            folder_reads.list_fixture_folders(
                fixture,
                readiness=_ready_report(),
                folders=catalog,
            )
        except ValueError as exc:
            assert expected in str(exc)
        else:
            raise AssertionError(f"invalid folder catalog accepted: {catalog!r}")


def test_cyclic_folder_hierarchy_fails_closed() -> None:
    fixture = mock_ui.default_outlook_fixture()
    cyclic = (
        folder_reads.SyntheticFolder(
            folder_key="inbox",
            display_name="Inbox",
            parent_key="archive",
        ),
        folder_reads.SyntheticFolder(
            folder_key="archive",
            display_name="Archive",
            parent_key="inbox",
        ),
        folder_reads.SyntheticFolder(folder_key="sent", display_name="Sent"),
    )

    try:
        folder_reads.list_fixture_folders(
            fixture,
            readiness=_ready_report(),
            folders=cyclic,
        )
    except ValueError as exc:
        assert "cycle" in str(exc) or "bounded depth" in str(exc)
    else:
        raise AssertionError("cyclic folder hierarchy must fail closed")


def test_folder_token_validation_is_bounded() -> None:
    invalid = (
        {"folder_key": "bad key"},
        {"folder_key": " inbox"},
        {"folder_key": ""},
        {"display_name": " "},
        {"parent_key": "bad parent"},
        {"folder_key": "inbox", "parent_key": "inbox"},
    )
    for overrides in invalid:
        values: dict[str, object] = {
            "folder_key": "inbox",
            "display_name": "Inbox",
            "parent_key": None,
        }
        values.update(overrides)
        try:
            folder_reads.SyntheticFolder(**values)  # type: ignore[arg-type]
        except ValueError:
            pass
        else:
            raise AssertionError(f"invalid folder definition accepted: {values!r}")


def test_unknown_folder_navigation_fails_closed() -> None:
    fixture = mock_ui.default_outlook_fixture()
    for folder_key, expected in (
        ("not-a-folder", "unknown synthetic folder_key"),
        (" inbox", "non-empty semantic token"),
        ("", "non-empty semantic token"),
    ):
        try:
            folder_reads.navigate_fixture_folder(
                fixture,
                folder_key,
                readiness=_ready_report(),
            )
        except ValueError as exc:
            assert expected in str(exc)
        else:
            raise AssertionError(f"invalid navigation target accepted: {folder_key!r}")


def test_out016_keeps_outlook_activation_absent() -> None:
    assert default_tool_registry().by_application("outlook") == ()
    assert default_capability_registry().by_application("outlook") == ()
