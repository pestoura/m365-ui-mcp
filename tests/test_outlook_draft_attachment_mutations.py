from __future__ import annotations

import pytest

from m365_mcp.application_registry import (
    ApplicationKey,
    ApplicationState,
    default_application_registry,
)
from m365_mcp.apps.outlook import draft_attachment_mutations, draft_models, readiness
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


def _catalog() -> tuple[draft_attachment_mutations.SyntheticDraftAttachment, ...]:
    return (
        draft_attachment_mutations.SyntheticDraftAttachment(
            "attachment-001",
            "synthetic-note.txt",
            128,
            "artifact-001",
        ),
    )


def test_add_and_remove_attachment_reference_are_verified() -> None:
    drafts = draft_models.default_synthetic_drafts()
    drafts, added = draft_attachment_mutations.apply_draft_attachment_mutation(
        drafts,
        draft_attachment_mutations.DraftAttachmentRequest(
            draft_attachment_mutations.DraftAttachmentAction.ADD,
            "draft-001",
            "attachment-001",
        ),
        readiness=_ready(),
        catalog=_catalog(),
    )
    assert drafts[0].attachment_keys == ("attachment-001",)
    assert added.verified is True

    drafts, removed = draft_attachment_mutations.apply_draft_attachment_mutation(
        drafts,
        draft_attachment_mutations.DraftAttachmentRequest(
            draft_attachment_mutations.DraftAttachmentAction.REMOVE,
            "draft-001",
            "attachment-001",
        ),
        readiness=_ready(),
        catalog=_catalog(),
    )
    assert drafts[0].attachment_keys == ()
    assert removed.verified is True


def test_add_requires_controlled_artifact_catalog_entry() -> None:
    with pytest.raises(ValueError, match="controlled artifact catalog"):
        draft_attachment_mutations.apply_draft_attachment_mutation(
            draft_models.default_synthetic_drafts(),
            draft_attachment_mutations.DraftAttachmentRequest(
                draft_attachment_mutations.DraftAttachmentAction.ADD,
                "draft-001",
                "attachment-missing",
            ),
            readiness=_ready(),
            catalog=_catalog(),
        )


def test_repeated_add_and_remove_are_domain_idempotent() -> None:
    draft = draft_models.SyntheticDraft(
        "draft-001",
        attachment_keys=("attachment-001",),
    )
    unchanged, result = draft_attachment_mutations.apply_draft_attachment_mutation(
        (draft,),
        draft_attachment_mutations.DraftAttachmentRequest(
            draft_attachment_mutations.DraftAttachmentAction.ADD,
            "draft-001",
            "attachment-001",
        ),
        readiness=_ready(),
        catalog=_catalog(),
    )
    assert unchanged == (draft,)
    assert result.changed is False


def test_attachment_request_binds_to_core_idempotency_and_lock() -> None:
    request = draft_attachment_mutations.DraftAttachmentRequest(
        draft_attachment_mutations.DraftAttachmentAction.ADD,
        "draft-001",
        "attachment-001",
    )
    identity = resource_state_identity(
        ApplicationKey.OUTLOOK,
        account_scope="professional_session",
        container_kind="folder",
        external_container_id="drafts",
        resource_kind="draft",
        external_resource_id=request.draft_key,
    )
    record = reserve_operation(
        "outlook_draft_attachment",
        identity,
        request.to_payload(),
        read_back_required=True,
    )
    lock = state_lock("mock-professional-account", identity)
    assert record.read_back_required is True
    assert lock.state_identity_digest == identity.identity_digest


def test_out044_remains_reserved_and_not_public() -> None:
    outlook = default_application_registry().get(ApplicationKey.OUTLOOK)
    assert outlook.state is ApplicationState.RESERVED
    assert default_tool_registry().by_application("outlook") == ()
