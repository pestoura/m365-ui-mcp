from __future__ import annotations

import pytest

from m365_mcp.application_registry import (
    ApplicationKey,
    ApplicationState,
    default_application_registry,
)
from m365_mcp.apps.outlook import contact_list_mutations, contact_list_reads, mock_ui, readiness
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


def test_contact_list_create_update_delete_have_read_back() -> None:
    fixture = mock_ui.default_outlook_fixture()
    lists: tuple[contact_list_reads.SyntheticContactList, ...] = ()
    lists, created = contact_list_mutations.apply_contact_list_mutation(
        fixture,
        lists,
        contact_list_mutations.ContactListMutationRequest(
            contact_list_mutations.ContactListAction.CREATE,
            "list-alpha",
            "Alpha Contacts",
        ),
        readiness=_ready(),
    )
    assert created.exists_after is True
    lists, updated = contact_list_mutations.apply_contact_list_mutation(
        fixture,
        lists,
        contact_list_mutations.ContactListMutationRequest(
            contact_list_mutations.ContactListAction.UPDATE,
            "list-alpha",
            "Alpha Team",
        ),
        readiness=_ready(),
    )
    assert updated.read_back is not None
    assert updated.read_back.display_name == "Alpha Team"
    lists, deleted = contact_list_mutations.apply_contact_list_mutation(
        fixture,
        lists,
        contact_list_mutations.ContactListMutationRequest(
            contact_list_mutations.ContactListAction.DELETE,
            "list-alpha",
        ),
        readiness=_ready(),
    )
    assert lists == ()
    assert deleted.exists_after is False
    assert deleted.verified is True


def test_contact_list_update_preserves_members() -> None:
    fixture = mock_ui.default_outlook_fixture()
    existing = contact_list_reads.SyntheticContactList(
        "list-alpha",
        "Alpha Contacts",
        ("person-alpha", "person-bravo"),
    )
    lists, result = contact_list_mutations.apply_contact_list_mutation(
        fixture,
        (existing,),
        contact_list_mutations.ContactListMutationRequest(
            contact_list_mutations.ContactListAction.UPDATE,
            "list-alpha",
            "Renamed Contacts",
        ),
        readiness=_ready(),
    )
    assert result.read_back is not None
    assert result.read_back.member_keys == existing.member_keys
    assert lists[0].member_keys == existing.member_keys


def test_contact_list_create_and_delete_are_idempotent() -> None:
    fixture = mock_ui.default_outlook_fixture()
    existing = contact_list_reads.SyntheticContactList("list-alpha", "Alpha Contacts", ())
    lists, repeat = contact_list_mutations.apply_contact_list_mutation(
        fixture,
        (existing,),
        contact_list_mutations.ContactListMutationRequest(
            contact_list_mutations.ContactListAction.CREATE,
            "list-alpha",
            "Alpha Contacts",
        ),
        readiness=_ready(),
    )
    assert lists == (existing,)
    assert repeat.changed is False
    _, absent = contact_list_mutations.apply_contact_list_mutation(
        fixture,
        (),
        contact_list_mutations.ContactListMutationRequest(
            contact_list_mutations.ContactListAction.DELETE,
            "list-alpha",
        ),
        readiness=_ready(),
    )
    assert absent.changed is False


def test_contact_list_update_missing_fails_closed() -> None:
    with pytest.raises(ValueError, match="not found"):
        contact_list_mutations.apply_contact_list_mutation(
            mock_ui.default_outlook_fixture(),
            (),
            contact_list_mutations.ContactListMutationRequest(
                contact_list_mutations.ContactListAction.UPDATE,
                "list-alpha",
                "Alpha Contacts",
            ),
            readiness=_ready(),
        )


def test_out102_remains_reserved_and_not_public() -> None:
    outlook = default_application_registry().get(ApplicationKey.OUTLOOK)
    assert outlook.state is ApplicationState.RESERVED
    assert default_tool_registry().by_application("outlook") == ()
