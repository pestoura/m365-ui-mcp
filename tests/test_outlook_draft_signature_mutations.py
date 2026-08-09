from __future__ import annotations

import pytest

from m365_mcp.application_registry import (
    ApplicationKey,
    ApplicationState,
    default_application_registry,
)
from m365_mcp.apps.outlook import draft_models, draft_signature_mutations, readiness
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


def _signatures() -> tuple[draft_signature_mutations.SyntheticSignature, ...]:
    return (
        draft_signature_mutations.SyntheticSignature("signature-default"),
        draft_signature_mutations.SyntheticSignature("signature-disabled", False),
    )


def test_apply_and_clear_known_signature_are_verified() -> None:
    drafts = draft_models.default_synthetic_drafts()
    drafts, applied = draft_signature_mutations.apply_draft_signature(
        drafts,
        draft_signature_mutations.DraftSignatureRequest(
            draft_signature_mutations.DraftSignatureAction.APPLY,
            "draft-001",
            "signature-default",
        ),
        readiness=_ready(),
        signatures=_signatures(),
    )
    assert drafts[0].signature_key == "signature-default"
    assert applied.verified is True

    drafts, cleared = draft_signature_mutations.apply_draft_signature(
        drafts,
        draft_signature_mutations.DraftSignatureRequest(
            draft_signature_mutations.DraftSignatureAction.CLEAR,
            "draft-001",
        ),
        readiness=_ready(),
        signatures=_signatures(),
    )
    assert drafts[0].signature_key is None
    assert cleared.verified is True


def test_unknown_or_disabled_signature_fails_closed() -> None:
    drafts = draft_models.default_synthetic_drafts()
    with pytest.raises(ValueError, match="exactly one"):
        draft_signature_mutations.apply_draft_signature(
            drafts,
            draft_signature_mutations.DraftSignatureRequest(
                draft_signature_mutations.DraftSignatureAction.APPLY,
                "draft-001",
                "signature-missing",
            ),
            readiness=_ready(),
            signatures=_signatures(),
        )
    with pytest.raises(ValueError, match="not enabled"):
        draft_signature_mutations.apply_draft_signature(
            drafts,
            draft_signature_mutations.DraftSignatureRequest(
                draft_signature_mutations.DraftSignatureAction.APPLY,
                "draft-001",
                "signature-disabled",
            ),
            readiness=_ready(),
            signatures=_signatures(),
        )


def test_repeated_signature_apply_is_domain_idempotent() -> None:
    draft = draft_models.SyntheticDraft(
        "draft-001",
        signature_key="signature-default",
    )
    unchanged, result = draft_signature_mutations.apply_draft_signature(
        (draft,),
        draft_signature_mutations.DraftSignatureRequest(
            draft_signature_mutations.DraftSignatureAction.APPLY,
            "draft-001",
            "signature-default",
        ),
        readiness=_ready(),
        signatures=_signatures(),
    )
    assert unchanged == (draft,)
    assert result.changed is False


def test_signature_request_binds_to_core_idempotency_and_lock() -> None:
    request = draft_signature_mutations.DraftSignatureRequest(
        draft_signature_mutations.DraftSignatureAction.APPLY,
        "draft-001",
        "signature-default",
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
        "outlook_draft_signature",
        identity,
        request.to_payload(),
        read_back_required=True,
    )
    lock = state_lock("mock-professional-account", identity)
    assert record.read_back_required is True
    assert lock.state_identity_digest == identity.identity_digest


def test_out046_remains_reserved_and_not_public() -> None:
    outlook = default_application_registry().get(ApplicationKey.OUTLOOK)
    assert outlook.state is ApplicationState.RESERVED
    assert default_tool_registry().by_application("outlook") == ()
