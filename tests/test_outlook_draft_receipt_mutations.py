from __future__ import annotations

import pytest

from m365_mcp.application_registry import (
    ApplicationKey,
    ApplicationState,
    default_application_registry,
)
from m365_mcp.apps.outlook import draft_models, draft_receipt_mutations, readiness
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


def test_receipt_flags_are_applied_and_verified() -> None:
    drafts = draft_models.default_synthetic_drafts()
    drafts, result = draft_receipt_mutations.apply_draft_receipt_options(
        drafts,
        draft_receipt_mutations.DraftReceiptRequest(
            "draft-001",
            read_receipt_requested=True,
            delivery_receipt_requested=True,
        ),
        readiness=_ready(),
    )
    assert drafts[0].read_receipt_requested is True
    assert drafts[0].delivery_receipt_requested is True
    assert result.verified is True


def test_single_receipt_option_preserves_other_flag() -> None:
    draft = draft_models.SyntheticDraft(
        "draft-001",
        delivery_receipt_requested=True,
    )
    updated, result = draft_receipt_mutations.apply_draft_receipt_options(
        (draft,),
        draft_receipt_mutations.DraftReceiptRequest(
            "draft-001",
            read_receipt_requested=True,
        ),
        readiness=_ready(),
    )
    assert updated[0].read_receipt_requested is True
    assert updated[0].delivery_receipt_requested is True
    assert result.read_back_delivery_receipt_requested is True


def test_receipt_request_requires_at_least_one_option() -> None:
    with pytest.raises(ValueError, match="at least one"):
        draft_receipt_mutations.DraftReceiptRequest("draft-001")


def test_receipt_request_binds_to_core_idempotency_and_lock() -> None:
    request = draft_receipt_mutations.DraftReceiptRequest(
        "draft-001",
        read_receipt_requested=True,
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
        "outlook_draft_receipts",
        identity,
        request.to_payload(),
        read_back_required=True,
    )
    lock = state_lock("mock-professional-account", identity)
    assert record.read_back_required is True
    assert lock.state_identity_digest == identity.identity_digest


def test_out048_remains_reserved_and_not_public() -> None:
    outlook = default_application_registry().get(ApplicationKey.OUTLOOK)
    assert outlook.state is ApplicationState.RESERVED
    assert default_tool_registry().by_application("outlook") == ()
