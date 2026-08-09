from __future__ import annotations

import pytest

from m365_mcp.apps.outlook import contact_list_reads, mock_ui, readiness
from m365_mcp.capability_registry import default_capability_registry
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


def test_list_and_get_contact_lists() -> None:
    fixture = mock_ui.default_outlook_fixture()
    lists = contact_list_reads.list_fixture_contact_lists(
        fixture,
        readiness=_ready(),
    )
    assert [item.list_key for item in lists] == ["list-security", "list-platform"]
    selected = contact_list_reads.get_fixture_contact_list(
        fixture,
        "list-security",
        readiness=_ready(),
    )
    assert selected.member_keys == ("person-alpha", "person-charlie")
    assert selected.to_projection()["member_count"] == 2


def test_duplicate_members_and_unknown_list_fail_closed() -> None:
    with pytest.raises(ValueError, match="unique"):
        contact_list_reads.SyntheticContactList(
            "list-a",
            "A",
            ("person-a", "person-a"),
        )
    fixture = mock_ui.default_outlook_fixture()
    with pytest.raises(ValueError, match="not found"):
        contact_list_reads.get_fixture_contact_list(
            fixture,
            "missing",
            readiness=_ready(),
        )


def test_projection_excludes_identity_and_browser_primitives() -> None:
    fixture = mock_ui.default_outlook_fixture()
    selected = contact_list_reads.get_fixture_contact_list(
        fixture,
        "list-security",
        readiness=_ready(),
    )
    projection = repr(selected.to_projection()).lower()
    forbidden_values = (
        "@",
        "http",
        "://",
        "selector",
        "xpath",
        "javascript",
        "cookie",
        "tenant",
    )
    for forbidden in forbidden_values:
        assert forbidden not in projection


def test_out027_keeps_outlook_activation_absent() -> None:
    assert default_tool_registry().by_application("outlook") == ()
    assert default_capability_registry().by_application("outlook") == ()
