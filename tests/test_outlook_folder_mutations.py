from __future__ import annotations

import pytest

from m365_mcp.application_registry import (
    ApplicationKey,
    ApplicationState,
    default_application_registry,
)
from m365_mcp.apps.outlook import folder_mutations, folder_reads, mock_ui, readiness
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


def test_create_rename_and_favorite_are_verified() -> None:
    fixture = mock_ui.default_outlook_fixture()
    folders = folder_reads.default_synthetic_folders()
    created_fixture, created_folders, favorites, created = (
        folder_mutations.apply_fixture_folder_mutation(
            fixture,
            folder_mutations.FolderMutationRequest(
                folder_mutations.FolderMutationAction.CREATE,
                "projects",
                display_name="Projects",
                parent_key="inbox",
            ),
            readiness=_ready(),
            folders=folders,
        )
    )
    assert created.verified is True
    assert "projects" in created_fixture.folders

    renamed_fixture, renamed_folders, favorites, renamed = (
        folder_mutations.apply_fixture_folder_mutation(
            created_fixture,
            folder_mutations.FolderMutationRequest(
                folder_mutations.FolderMutationAction.RENAME,
                "projects",
                display_name="Active Projects",
            ),
            readiness=_ready(),
            folders=created_folders,
            favorite_folder_keys=favorites,
        )
    )
    assert renamed_fixture == created_fixture
    assert renamed.read_back_display_name == "Active Projects"

    _, final_folders, favorites, favored = folder_mutations.apply_fixture_folder_mutation(
        renamed_fixture,
        folder_mutations.FolderMutationRequest(
            folder_mutations.FolderMutationAction.FAVORITE,
            "projects",
        ),
        readiness=_ready(),
        folders=renamed_folders,
        favorite_folder_keys=favorites,
    )
    assert final_folders == renamed_folders
    assert favorites == ("projects",)
    assert favored.read_back_favorite is True


def test_favorite_and_unfavorite_are_domain_idempotent() -> None:
    fixture = mock_ui.default_outlook_fixture()
    folders = folder_reads.default_synthetic_folders()
    _, _, favorites, favored = folder_mutations.apply_fixture_folder_mutation(
        fixture,
        folder_mutations.FolderMutationRequest(
            folder_mutations.FolderMutationAction.FAVORITE,
            "inbox",
        ),
        readiness=_ready(),
        folders=folders,
        favorite_folder_keys=("inbox",),
    )
    assert favorites == ("inbox",)
    assert favored.changed is False

    _, _, favorites, unfavored = folder_mutations.apply_fixture_folder_mutation(
        fixture,
        folder_mutations.FolderMutationRequest(
            folder_mutations.FolderMutationAction.UNFAVORITE,
            "inbox",
        ),
        readiness=_ready(),
        folders=folders,
        favorite_folder_keys=(),
    )
    assert favorites == ()
    assert unfavored.changed is False


def test_protected_folder_rename_is_blocked() -> None:
    fixture = mock_ui.default_outlook_fixture()
    with pytest.raises(ValueError, match="protected"):
        folder_mutations.apply_fixture_folder_mutation(
            fixture,
            folder_mutations.FolderMutationRequest(
                folder_mutations.FolderMutationAction.RENAME,
                "inbox",
                display_name="Changed Inbox",
            ),
            readiness=_ready(),
            folders=folder_reads.default_synthetic_folders(),
        )


def test_folder_request_binds_to_core_idempotency_and_resource_lock() -> None:
    request = folder_mutations.FolderMutationRequest(
        folder_mutations.FolderMutationAction.FAVORITE,
        "inbox",
    )
    identity = resource_state_identity(
        ApplicationKey.OUTLOOK,
        account_scope="professional_session",
        container_kind="mailbox",
        external_container_id="mock-primary",
        resource_kind="folder",
        external_resource_id=request.folder_key,
    )
    record = reserve_operation(
        "outlook_folder_favorite",
        identity,
        request.to_payload(),
        read_back_required=True,
    )
    lock = state_lock("mock-professional-account", identity)
    assert record.read_back_required is True
    assert lock.state_identity_digest == identity.identity_digest


def test_out039_remains_reserved_and_not_public() -> None:
    outlook = default_application_registry().get(ApplicationKey.OUTLOOK)
    assert outlook.state is ApplicationState.RESERVED
    assert default_tool_registry().by_application("outlook") == ()
