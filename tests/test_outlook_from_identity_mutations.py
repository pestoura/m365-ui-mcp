from __future__ import annotations

import pytest

from m365_mcp.application_registry import (
    ApplicationKey,
    ApplicationState,
    default_application_registry,
)
from m365_mcp.apps.outlook import draft_models, from_identity_mutations, readiness
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


def _identities() -> tuple[from_identity_mutations.SyntheticFromIdentity, ...]:
    return (
        from_identity_mutations.SyntheticFromIdentity(
            "primary",
            from_identity_mutations.FromIdentityMode.PRIMARY,
            True,
        ),
        from_identity_mutations.SyntheticFromIdentity(
            "shared-alpha",
            from_identity_mutations.FromIdentityMode.SHARED,
            True,
        ),
        from_identity_mutations.SyntheticFromIdentity(
            "delegated-blocked",
            from_identity_mutations.FromIdentityMode.DELEGATED,
            False,
        ),
    )


def test_authorized_from_identity_is_selected_and_verified() -> None:
    drafts = draft_models.default_synthetic_drafts()
    drafts, result = from_identity_mutations.select_from_identity(
        drafts,
        from_identity_mutations.FromIdentityRequest("draft-001", "shared-alpha"),
        readiness=_ready(),
        identities=_identities(),
    )
    assert drafts[0].from_identity_key == "shared-alpha"
    assert result.mode is from_identity_mutations.FromIdentityMode.SHARED
    assert result.verified is True


def test_unauthorized_and_unknown_from_identity_fail_closed() -> None:
    drafts = draft_models.default_synthetic_drafts()
    with pytest.raises(ValueError, match="not authorized"):
        from_identity_mutations.select_from_identity(
            drafts,
            from_identity_mutations.FromIdentityRequest(
                "draft-001",
                "delegated-blocked",
            ),
            readiness=_ready(),
            identities=_identities(),
        )
    with pytest.raises(ValueError, match="exactly one"):
        from_identity_mutations.select_from_identity(
            drafts,
            from_identity_mutations.FromIdentityRequest("draft-001", "missing"),
            readiness=_ready(),
            identities=_identities(),
        )


def test_repeated_from_selection_is_domain_idempotent() -> None:
    drafts = draft_models.default_synthetic_drafts()
    unchanged, result = from_identity_mutations.select_from_identity(
        drafts,
        from_identity_mutations.FromIdentityRequest("draft-001", "primary"),
        readiness=_ready(),
        identities=_identities(),
    )
    assert unchanged == drafts
    assert result.changed is False


def test_from_request_binds_to_core_idempotency_and_lock() -> None:
    request = from_identity_mutations.FromIdentityRequest("draft-001", "shared-alpha")
    identity = resource_state_identity(
        ApplicationKey.OUTLOOK,
        account_scope="professional_session",
        container_kind="folder",
        external_container_id="drafts",
        resource_kind="draft",
        external_resource_id=request.draft_key,
    )
    record = reserve_operation(
        "outlook_draft_from_identity",
        identity,
        request.to_payload(),
        read_back_required=True,
    )
    lock = state_lock("mock-professional-account", identity)
    assert record.read_back_required is True
    assert lock.state_identity_digest == identity.identity_digest


def test_out043_remains_reserved_and_not_public() -> None:
    outlook = default_application_registry().get(ApplicationKey.OUTLOOK)
    assert outlook.state is ApplicationState.RESERVED
    assert default_tool_registry().by_application("outlook") == ()
