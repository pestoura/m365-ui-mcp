from __future__ import annotations

import pytest

from m365_mcp.application_registry import (
    ApplicationKey,
    ApplicationState,
    default_application_registry,
)
from m365_mcp.apps.outlook import (
    draft_models,
    from_identity_mutations,
    readiness,
    shared_mailbox_context,
    shared_mailbox_send_as,
)
from m365_mcp.tool_registry import default_tool_registry


def _ready() -> readiness.OutlookReadinessReport:
    return readiness.OutlookReadinessReport(
        state=readiness.OutlookReadinessState.DISCOVERY_READY,
        primary_context_verified=True,
        shared_context_verified=True,
        candidate_count=1,
        observed_count=1,
        blocked_count=0,
        reattestation_count=0,
    )


def _context(valid: bool = True) -> shared_mailbox_context.SharedMailboxContext:
    return shared_mailbox_context.SharedMailboxContext(
        state=(
            shared_mailbox_context.SharedMailboxContextState.VERIFIED
            if valid
            else shared_mailbox_context.SharedMailboxContextState.UNVERIFIED
        ),
        primary_context_verified=True,
        shared_shell_verified=valid,
        scope_digest="a" * 64 if valid else None,
        evidence_digest="b" * 64 if valid else None,
    )


def _identities() -> tuple[from_identity_mutations.SyntheticFromIdentity, ...]:
    return (
        from_identity_mutations.SyntheticFromIdentity(
            "shared-alpha",
            from_identity_mutations.FromIdentityMode.SHARED,
            True,
        ),
        from_identity_mutations.SyntheticFromIdentity(
            "delegated-alpha",
            from_identity_mutations.FromIdentityMode.DELEGATED,
            True,
        ),
    )


def test_send_as_prepares_governed_non_executable_intent() -> None:
    drafts, intent, result = shared_mailbox_send_as.prepare_shared_mailbox_send_as(
        _context(),
        draft_models.default_synthetic_drafts(),
        draft_key="draft-001",
        identity_key="shared-alpha",
        readiness=_ready(),
        identities=_identities(),
    )
    assert drafts[0].from_identity_key == "shared-alpha"
    assert result.verified is True
    assert result.dispatched is False
    assert intent.executable is False
    assert intent.to_projection()["approval_required"] is True


def test_send_as_fails_closed_for_scope_mode_and_address_shape() -> None:
    with pytest.raises(ValueError, match="verified shared mailbox context"):
        shared_mailbox_send_as.prepare_shared_mailbox_send_as(
            _context(False),
            draft_models.default_synthetic_drafts(),
            draft_key="draft-001",
            identity_key="shared-alpha",
            readiness=_ready(),
            identities=_identities(),
        )
    with pytest.raises(ValueError, match="SHARED"):
        shared_mailbox_send_as.prepare_shared_mailbox_send_as(
            _context(),
            draft_models.default_synthetic_drafts(),
            draft_key="draft-001",
            identity_key="delegated-alpha",
            readiness=_ready(),
            identities=_identities(),
        )
    with pytest.raises(ValueError, match="must not encode an address"):
        shared_mailbox_send_as.prepare_shared_mailbox_send_as(
            _context(),
            draft_models.default_synthetic_drafts(),
            draft_key="draft-001",
            identity_key="shared@example.test",
            readiness=_ready(),
            identities=_identities(),
        )


def test_out116_remains_reserved_and_not_public() -> None:
    outlook = default_application_registry().get(ApplicationKey.OUTLOOK)
    assert outlook.state is ApplicationState.RESERVED
    assert default_tool_registry().by_application("outlook") == ()
