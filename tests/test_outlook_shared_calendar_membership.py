from __future__ import annotations

import pytest

from m365_mcp.application_registry import (
    ApplicationKey,
    ApplicationState,
    default_application_registry,
)
from m365_mcp.apps.outlook import readiness, shared_calendar_membership
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


def _unready() -> readiness.OutlookReadinessReport:
    return readiness.OutlookReadinessReport(
        state=readiness.OutlookReadinessState.FOUNDATION_READY,
        primary_context_verified=True,
        shared_context_verified=False,
        candidate_count=1,
        observed_count=0,
        blocked_count=0,
        reattestation_count=0,
    )


def test_membership_add_remove_are_idempotent_and_read_back() -> None:
    members, added = shared_calendar_membership.apply_shared_calendar_membership(
        (),
        shared_calendar_membership.MembershipRequest(
            shared_calendar_membership.MembershipAction.ADD,
            "calendar-alpha",
            "member-alpha",
        ),
        readiness=_ready(),
    )
    assert added.previous_is_member is False
    assert added.read_back_is_member is True
    assert added.changed is True
    assert added.verified is True

    members, duplicate = shared_calendar_membership.apply_shared_calendar_membership(
        members,
        shared_calendar_membership.MembershipRequest(
            shared_calendar_membership.MembershipAction.ADD,
            "calendar-alpha",
            "member-alpha",
        ),
        readiness=_ready(),
    )
    assert duplicate.changed is False

    members, removed = shared_calendar_membership.apply_shared_calendar_membership(
        members,
        shared_calendar_membership.MembershipRequest(
            shared_calendar_membership.MembershipAction.REMOVE,
            "calendar-alpha",
            "member-alpha",
        ),
        readiness=_ready(),
    )
    assert removed.read_back_is_member is False
    assert removed.changed is True
    _, absent = shared_calendar_membership.apply_shared_calendar_membership(
        members,
        shared_calendar_membership.MembershipRequest(
            shared_calendar_membership.MembershipAction.REMOVE,
            "calendar-alpha",
            "member-alpha",
        ),
        readiness=_ready(),
    )
    assert absent.changed is False


def test_membership_read_order_is_deterministic() -> None:
    members = (
        shared_calendar_membership.SharedCalendarMember("calendar-alpha", "member-charlie"),
        shared_calendar_membership.SharedCalendarMember("calendar-alpha", "member-alpha"),
        shared_calendar_membership.SharedCalendarMember("calendar-alpha", "member-bravo"),
    )
    state = shared_calendar_membership.read_shared_calendar_membership(
        members,
        calendar_key="calendar-alpha",
        readiness=_ready(),
    )
    assert state.member_keys == ("member-alpha", "member-bravo", "member-charlie")
    assert state.member_count == 3


def test_membership_rejects_identity_shape_duplicates_and_unready() -> None:
    with pytest.raises(ValueError, match="address identity"):
        shared_calendar_membership.SharedCalendarMember(
            "calendar-alpha",
            "someone@example.invalid",
        )
    duplicate = (
        shared_calendar_membership.SharedCalendarMember("calendar-alpha", "member-alpha"),
        shared_calendar_membership.SharedCalendarMember("calendar-alpha", "member-alpha"),
    )
    with pytest.raises(ValueError, match="duplicate relation"):
        shared_calendar_membership.read_shared_calendar_membership(
            duplicate,
            calendar_key="calendar-alpha",
            readiness=_ready(),
        )
    with pytest.raises(ValueError, match="not ready"):
        shared_calendar_membership.read_shared_calendar_membership(
            (),
            calendar_key="calendar-alpha",
            readiness=_unready(),
        )


def test_out095_remains_reserved_and_not_public() -> None:
    outlook = default_application_registry().get(ApplicationKey.OUTLOOK)
    assert outlook.state is ApplicationState.RESERVED
    assert default_tool_registry().by_application("outlook") == ()


def test_out095_result_contains_no_live_or_browser_material() -> None:
    _, result = shared_calendar_membership.apply_shared_calendar_membership(
        (),
        shared_calendar_membership.MembershipRequest(
            shared_calendar_membership.MembershipAction.ADD,
            "calendar-alpha",
            "member-alpha",
        ),
        readiness=_ready(),
    )
    rendered = repr(result).lower()
    for marker in (
        "https://",
        "http://",
        "selector",
        "xpath",
        "css=",
        "cookie",
        "token",
        "graph.microsoft",
        "@",
    ):
        assert marker not in rendered
