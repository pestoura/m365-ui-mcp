from __future__ import annotations

import pytest

from m365_mcp.application_registry import ApplicationKey, ApplicationState, default_application_registry
from m365_mcp.apps.outlook import draft_models, readiness, recipient_resolution
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


def _candidates() -> tuple[recipient_resolution.SyntheticRecipientCandidate, ...]:
    return (
        recipient_resolution.SyntheticRecipientCandidate("person-alpha", ("alpha", "project-a")),
        recipient_resolution.SyntheticRecipientCandidate("person-beta", ("beta", "project-b")),
    )


def test_to_cc_bcc_resolution_is_explicit_and_verified() -> None:
    drafts = draft_models.default_synthetic_drafts()
    drafts, result = recipient_resolution.apply_recipient_assignment(
        drafts,
        recipient_resolution.RecipientAssignmentRequest(
            "draft-001",
            recipient_resolution.RecipientField.TO,
            ("alpha", "person-beta"),
        ),
        readiness=_ready(),
        candidates=_candidates(),
    )
    assert result.resolved_keys == ("person-alpha", "person-beta")
    assert drafts[0].to_keys == result.resolved_keys
    assert result.verified is True


def test_ambiguous_recipient_resolution_fails_closed() -> None:
    candidates = (
        recipient_resolution.SyntheticRecipientCandidate("person-one", ("shared",)),
        recipient_resolution.SyntheticRecipientCandidate("person-two", ("shared",)),
    )
    with pytest.raises(ValueError, match="ambiguous"):
        recipient_resolution.resolve_recipient("shared", candidates)


def test_unknown_and_duplicate_resolution_fail_closed() -> None:
    with pytest.raises(ValueError, match="did not resolve"):
        recipient_resolution.resolve_recipient("missing", _candidates())
    with pytest.raises(ValueError, match="duplicate"):
        recipient_resolution.apply_recipient_assignment(
            draft_models.default_synthetic_drafts(),
            recipient_resolution.RecipientAssignmentRequest(
                "draft-001",
                recipient_resolution.RecipientField.CC,
                ("alpha", "person-alpha"),
            ),
            readiness=_ready(),
            candidates=_candidates(),
        )


def test_recipient_request_binds_to_core_idempotency_and_lock() -> None:
    request = recipient_resolution.RecipientAssignmentRequest(
        "draft-001",
        recipient_resolution.RecipientField.BCC,
        ("alpha",),
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
        "outlook_draft_recipients",
        identity,
        request.to_payload(),
        read_back_required=True,
    )
    lock = state_lock("mock-professional-account", identity)
    assert record.read_back_required is True
    assert lock.state_identity_digest == identity.identity_digest


def test_out042_remains_reserved_and_not_public() -> None:
    outlook = default_application_registry().get(ApplicationKey.OUTLOOK)
    assert outlook.state is ApplicationState.RESERVED
    assert default_tool_registry().by_application("outlook") == ()
