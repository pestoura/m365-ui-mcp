from __future__ import annotations

import pytest

from m365_mcp.application_registry import (
    ApplicationKey,
    ApplicationState,
    default_application_registry,
)
from m365_mcp.apps.outlook import (
    contact_list_membership,
    contact_list_reads,
    mock_ui,
    people_reads,
    readiness,
)
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


def _contacts() -> tuple[people_reads.SyntheticContact, ...]:
    return (
        people_reads.SyntheticContact("person-alpha", "Alex Example"),
        people_reads.SyntheticContact("person-bravo", "Bea Sample"),
    )


def _lists() -> tuple[contact_list_reads.SyntheticContactList, ...]:
    return (
        contact_list_reads.SyntheticContactList(
            "list-alpha",
            "Alpha Contacts",
            ("person-alpha",),
        ),
    )


def test_contact_list_membership_add_remove_are_idempotent_and_read_back() -> None:
    fixture = mock_ui.default_outlook_fixture()
    lists, added = contact_list_membership.apply_contact_list_membership(
        fixture,
        _contacts(),
        _lists(),
        contact_list_membership.ContactListMembershipRequest(
            contact_list_membership.ContactListMembershipAction.ADD,
            "list-alpha",
            "person-bravo",
        ),
        readiness=_ready(),
    )
    assert added.read_back_is_member is True
    assert added.member_count == 2
    lists, repeat = contact_list_membership.apply_contact_list_membership(
        fixture,
        _contacts(),
        lists,
        contact_list_membership.ContactListMembershipRequest(
            contact_list_membership.ContactListMembershipAction.ADD,
            "list-alpha",
            "person-bravo",
        ),
        readiness=_ready(),
    )
    assert repeat.changed is False
    lists, removed = contact_list_membership.apply_contact_list_membership(
        fixture,
        _contacts(),
        lists,
        contact_list_membership.ContactListMembershipRequest(
            contact_list_membership.ContactListMembershipAction.REMOVE,
            "list-alpha",
            "person-bravo",
        ),
        readiness=_ready(),
    )
    assert removed.read_back_is_member is False
    _, absent = contact_list_membership.apply_contact_list_membership(
        fixture,
        _contacts(),
        lists,
        contact_list_membership.ContactListMembershipRequest(
            contact_list_membership.ContactListMembershipAction.REMOVE,
            "list-alpha",
            "person-bravo",
        ),
        readiness=_ready(),
    )
    assert absent.changed is False


def test_contact_list_membership_requires_existing_contact_and_list() -> None:
    fixture = mock_ui.default_outlook_fixture()
    with pytest.raises(ValueError, match="contact_key not found"):
        contact_list_membership.apply_contact_list_membership(
            fixture,
            (),
            _lists(),
            contact_list_membership.ContactListMembershipRequest(
                contact_list_membership.ContactListMembershipAction.ADD,
                "list-alpha",
                "person-bravo",
            ),
            readiness=_ready(),
        )
    with pytest.raises(ValueError, match="list_key not found"):
        contact_list_membership.apply_contact_list_membership(
            fixture,
            _contacts(),
            (),
            contact_list_membership.ContactListMembershipRequest(
                contact_list_membership.ContactListMembershipAction.ADD,
                "list-alpha",
                "person-bravo",
            ),
            readiness=_ready(),
        )


def test_contact_list_members_are_sorted_after_add() -> None:
    fixture = mock_ui.default_outlook_fixture()
    lists = (
        contact_list_reads.SyntheticContactList(
            "list-alpha",
            "Alpha Contacts",
            ("person-bravo",),
        ),
    )
    updated, _ = contact_list_membership.apply_contact_list_membership(
        fixture,
        _contacts(),
        lists,
        contact_list_membership.ContactListMembershipRequest(
            contact_list_membership.ContactListMembershipAction.ADD,
            "list-alpha",
            "person-alpha",
        ),
        readiness=_ready(),
    )
    assert updated[0].member_keys == ("person-alpha", "person-bravo")


def test_out103_remains_reserved_and_not_public() -> None:
    outlook = default_application_registry().get(ApplicationKey.OUTLOOK)
    assert outlook.state is ApplicationState.RESERVED
    assert default_tool_registry().by_application("outlook") == ()
