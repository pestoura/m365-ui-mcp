from __future__ import annotations

import pytest

from m365_mcp.application_registry import (
    ApplicationKey,
    ApplicationState,
    default_application_registry,
)
from m365_mcp.apps.outlook import contact_mutations, mock_ui, people_reads, readiness
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


def test_contact_create_update_delete_have_exact_read_back() -> None:
    fixture = mock_ui.default_outlook_fixture()
    contacts: tuple[people_reads.SyntheticContact, ...] = ()
    contacts, created = contact_mutations.apply_contact_mutation(
        fixture,
        contacts,
        contact_mutations.ContactMutationRequest(
            contact_mutations.ContactAction.CREATE,
            "person-delta",
            "Dana Example",
            "Example Org",
            "Analyst",
        ),
        readiness=_ready(),
    )
    assert created.exists_after is True
    assert created.read_back is not None
    contacts, updated = contact_mutations.apply_contact_mutation(
        fixture,
        contacts,
        contact_mutations.ContactMutationRequest(
            contact_mutations.ContactAction.UPDATE,
            "person-delta",
            "Dana Example",
            "Example Org",
            "Senior Analyst",
        ),
        readiness=_ready(),
    )
    assert updated.read_back is not None
    assert updated.read_back.job_title == "Senior Analyst"
    contacts, deleted = contact_mutations.apply_contact_mutation(
        fixture,
        contacts,
        contact_mutations.ContactMutationRequest(
            contact_mutations.ContactAction.DELETE,
            "person-delta",
        ),
        readiness=_ready(),
    )
    assert contacts == ()
    assert deleted.exists_after is False
    assert deleted.verified is True


def test_contact_create_and_delete_are_idempotent() -> None:
    fixture = mock_ui.default_outlook_fixture()
    contact = people_reads.SyntheticContact("person-alpha", "Alex Example")
    contacts, repeat = contact_mutations.apply_contact_mutation(
        fixture,
        (contact,),
        contact_mutations.ContactMutationRequest(
            contact_mutations.ContactAction.CREATE,
            "person-alpha",
            "Alex Example",
        ),
        readiness=_ready(),
    )
    assert repeat.changed is False
    assert contacts == (contact,)
    _, absent = contact_mutations.apply_contact_mutation(
        fixture,
        (),
        contact_mutations.ContactMutationRequest(
            contact_mutations.ContactAction.DELETE,
            "person-alpha",
        ),
        readiness=_ready(),
    )
    assert absent.changed is False


def test_contact_mutations_fail_closed_on_key_conflict_and_missing_update() -> None:
    fixture = mock_ui.default_outlook_fixture()
    existing = people_reads.SyntheticContact("person-alpha", "Alex Example")
    with pytest.raises(ValueError, match="different state"):
        contact_mutations.apply_contact_mutation(
            fixture,
            (existing,),
            contact_mutations.ContactMutationRequest(
                contact_mutations.ContactAction.CREATE,
                "person-alpha",
                "Different Name",
            ),
            readiness=_ready(),
        )
    with pytest.raises(ValueError, match="not found"):
        contact_mutations.apply_contact_mutation(
            fixture,
            (),
            contact_mutations.ContactMutationRequest(
                contact_mutations.ContactAction.UPDATE,
                "person-alpha",
                "Alex Example",
            ),
            readiness=_ready(),
        )


def test_out100_remains_reserved_and_not_public() -> None:
    outlook = default_application_registry().get(ApplicationKey.OUTLOOK)
    assert outlook.state is ApplicationState.RESERVED
    assert default_tool_registry().by_application("outlook") == ()
