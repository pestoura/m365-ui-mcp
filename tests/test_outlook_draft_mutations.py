from __future__ import annotations

import pytest

from m365_mcp.application_registry import (
    ApplicationKey,
    ApplicationState,
    default_application_registry,
)
from m365_mcp.apps.outlook import draft_models, draft_mutations, readiness
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


def test_create_get_update_and_discard_are_verified() -> None:
    drafts = draft_models.default_synthetic_drafts()
    drafts, created = draft_mutations.apply_draft_mutation(
        drafts,
        draft_mutations.DraftMutationRequest(
            draft_mutations.DraftMutationAction.CREATE,
            "draft-002",
            subject="New synthetic draft",
        ),
        readiness=_ready(),
    )
    assert created.read_back_exists is True
    assert draft_mutations.get_synthetic_draft(drafts, "draft-002").subject == (
        "New synthetic draft"
    )

    drafts, updated = draft_mutations.apply_draft_mutation(
        drafts,
        draft_mutations.DraftMutationRequest(
            draft_mutations.DraftMutationAction.UPDATE,
            "draft-002",
            body_text="Updated synthetic body.",
        ),
        readiness=_ready(),
    )
    assert updated.changed is True
    assert draft_mutations.get_synthetic_draft(drafts, "draft-002").body_text == (
        "Updated synthetic body."
    )

    drafts, discarded = draft_mutations.apply_draft_mutation(
        drafts,
        draft_mutations.DraftMutationRequest(
            draft_mutations.DraftMutationAction.DISCARD,
            "draft-002",
        ),
        readiness=_ready(),
    )
    assert discarded.read_back_exists is False
    with pytest.raises(ValueError, match="draft_key"):
        draft_mutations.get_synthetic_draft(drafts, "draft-002")


def test_discard_is_domain_idempotent_when_already_absent() -> None:
    drafts = draft_models.default_synthetic_drafts()
    unchanged, result = draft_mutations.apply_draft_mutation(
        drafts,
        draft_mutations.DraftMutationRequest(
            draft_mutations.DraftMutationAction.DISCARD,
            "draft-missing",
        ),
        readiness=_ready(),
    )
    assert unchanged == drafts
    assert result.changed is False
    assert result.verified is True


def test_update_requires_material_change_input() -> None:
    with pytest.raises(ValueError, match="requires subject"):
        draft_mutations.DraftMutationRequest(
            draft_mutations.DraftMutationAction.UPDATE,
            "draft-001",
        )


def test_draft_request_binds_to_core_idempotency_and_resource_lock() -> None:
    request = draft_mutations.DraftMutationRequest(
        draft_mutations.DraftMutationAction.UPDATE,
        "draft-001",
        subject="Updated",
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
        "outlook_draft_update",
        identity,
        request.to_payload(),
        read_back_required=True,
    )
    lock = state_lock("mock-professional-account", identity)
    assert record.read_back_required is True
    assert lock.state_identity_digest == identity.identity_digest


def test_out041_remains_reserved_and_not_public() -> None:
    outlook = default_application_registry().get(ApplicationKey.OUTLOOK)
    assert outlook.state is ApplicationState.RESERVED
    assert default_tool_registry().by_application("outlook") == ()
