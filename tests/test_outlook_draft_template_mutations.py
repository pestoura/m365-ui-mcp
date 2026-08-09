from __future__ import annotations

import pytest

from m365_mcp.application_registry import (
    ApplicationKey,
    ApplicationState,
    default_application_registry,
)
from m365_mcp.apps.outlook import draft_models, draft_template_mutations, readiness
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


def _catalog() -> tuple[draft_template_mutations.SyntheticDraftInsert, ...]:
    return (
        draft_template_mutations.SyntheticDraftInsert(
            "snippet-status",
            "Synthetic status snippet.",
        ),
        draft_template_mutations.SyntheticDraftInsert(
            "template-update",
            "Synthetic template body.",
            subject="Synthetic template subject",
        ),
    )


def test_replace_and_append_insert_are_verified() -> None:
    drafts = draft_models.default_synthetic_drafts()
    drafts, replaced = draft_template_mutations.apply_draft_insert(
        drafts,
        draft_template_mutations.DraftInsertRequest(
            "draft-001",
            "template-update",
            draft_template_mutations.DraftInsertMode.REPLACE_BODY,
        ),
        readiness=_ready(),
        catalog=_catalog(),
    )
    assert drafts[0].subject == "Synthetic template subject"
    assert drafts[0].body_text == "Synthetic template body."
    assert replaced.verified is True

    drafts, appended = draft_template_mutations.apply_draft_insert(
        drafts,
        draft_template_mutations.DraftInsertRequest(
            "draft-001",
            "snippet-status",
            draft_template_mutations.DraftInsertMode.APPEND_BODY,
        ),
        readiness=_ready(),
        catalog=_catalog(),
    )
    assert drafts[0].body_text.endswith("Synthetic status snippet.")
    assert appended.verified is True


def test_unknown_or_duplicate_insert_fails_closed() -> None:
    drafts = draft_models.default_synthetic_drafts()
    with pytest.raises(ValueError, match="exactly one"):
        draft_template_mutations.apply_draft_insert(
            drafts,
            draft_template_mutations.DraftInsertRequest(
                "draft-001",
                "missing",
                draft_template_mutations.DraftInsertMode.REPLACE_BODY,
            ),
            readiness=_ready(),
            catalog=_catalog(),
        )


def test_insert_request_binds_to_core_idempotency_and_lock() -> None:
    request = draft_template_mutations.DraftInsertRequest(
        "draft-001",
        "snippet-status",
        draft_template_mutations.DraftInsertMode.APPEND_BODY,
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
        "outlook_draft_insert",
        identity,
        request.to_payload(),
        read_back_required=True,
    )
    lock = state_lock("mock-professional-account", identity)
    assert record.read_back_required is True
    assert lock.state_identity_digest == identity.identity_digest


def test_out047_remains_reserved_and_not_public() -> None:
    outlook = default_application_registry().get(ApplicationKey.OUTLOOK)
    assert outlook.state is ApplicationState.RESERVED
    assert default_tool_registry().by_application("outlook") == ()
