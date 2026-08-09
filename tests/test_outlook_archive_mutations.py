from __future__ import annotations

import pytest

from m365_mcp.application_registry import (
    ApplicationKey,
    ApplicationState,
    default_application_registry,
)
from m365_mcp.apps.outlook import archive_mutations, mock_ui, readiness
from m365_mcp.idempotency_v2 import reserve_operation
from m365_mcp.state_identity import resource_state_identity
from m365_mcp.tool_registry import default_tool_registry
from m365_mcp.typed_locks import state_lock


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


def test_archive_and_restore_are_verified() -> None:
    fixture = mock_ui.default_outlook_fixture()
    archived, first = archive_mutations.apply_fixture_archive_mutation(
        fixture,
        archive_mutations.ArchiveMutationRequest(
            archive_mutations.ArchiveMutationAction.ARCHIVE,
            "msg-001",
        ),
        readiness=_ready(),
    )
    assert first.previous_folder_key == "inbox"
    assert first.read_back_folder_key == "archive"
    assert first.changed is True
    assert first.verified is True

    restored, second = archive_mutations.apply_fixture_archive_mutation(
        archived,
        archive_mutations.ArchiveMutationRequest(
            archive_mutations.ArchiveMutationAction.RESTORE,
            "msg-001",
            restore_folder_key="inbox",
        ),
        readiness=_ready(),
    )
    restored_message = next(
        item for item in restored.messages if item.message_key == "msg-001"
    )
    assert second.read_back_folder_key == "inbox"
    assert second.verified is True
    assert restored_message.folder_key == "inbox"


def test_archive_and_restore_are_domain_idempotent() -> None:
    fixture = mock_ui.default_outlook_fixture()
    same_archive, first = archive_mutations.apply_fixture_archive_mutation(
        fixture,
        archive_mutations.ArchiveMutationRequest(
            archive_mutations.ArchiveMutationAction.ARCHIVE,
            "msg-002",
        ),
        readiness=_ready(),
    )
    assert same_archive == fixture
    assert first.changed is False

    same_inbox, second = archive_mutations.apply_fixture_archive_mutation(
        fixture,
        archive_mutations.ArchiveMutationRequest(
            archive_mutations.ArchiveMutationAction.RESTORE,
            "msg-001",
            restore_folder_key="inbox",
        ),
        readiness=_ready(),
    )
    assert same_inbox == fixture
    assert second.changed is False


def test_restore_requires_explicit_non_archive_target() -> None:
    with pytest.raises(ValueError, match="explicit restore_folder_key"):
        archive_mutations.ArchiveMutationRequest(
            archive_mutations.ArchiveMutationAction.RESTORE,
            "msg-002",
        )
    with pytest.raises(ValueError, match="must not be archive"):
        archive_mutations.ArchiveMutationRequest(
            archive_mutations.ArchiveMutationAction.RESTORE,
            "msg-002",
            restore_folder_key="archive",
        )


def test_archive_request_binds_to_core_idempotency_and_resource_lock() -> None:
    request = archive_mutations.ArchiveMutationRequest(
        archive_mutations.ArchiveMutationAction.ARCHIVE,
        "msg-001",
    )
    identity = resource_state_identity(
        ApplicationKey.OUTLOOK,
        account_scope="professional_session",
        container_kind="folder",
        external_container_id="inbox",
        resource_kind="message",
        external_resource_id=request.message_key,
    )
    record = reserve_operation(
        "outlook_archive",
        identity,
        request.to_payload(),
        read_back_required=True,
    )
    lock = state_lock("mock-professional-account", identity)
    assert record.read_back_required is True
    assert lock.state_identity_digest == identity.identity_digest


def test_out037_remains_reserved_and_not_public() -> None:
    outlook = default_application_registry().get(ApplicationKey.OUTLOOK)
    assert outlook.state is ApplicationState.RESERVED
    assert default_tool_registry().by_application("outlook") == ()
