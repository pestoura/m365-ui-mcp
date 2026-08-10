from __future__ import annotations

import pytest

from m365_mcp.application_registry import (
    ApplicationKey,
    ApplicationState,
    default_application_registry,
)
from m365_mcp.apps.outlook import shared_mailbox_context, shared_mailbox_discovery
from m365_mcp.tool_registry import default_tool_registry


def _context(*, valid: bool) -> shared_mailbox_context.SharedMailboxContext:
    if valid:
        return shared_mailbox_context.SharedMailboxContext(
            state=shared_mailbox_context.SharedMailboxContextState.VERIFIED,
            primary_context_verified=True,
            shared_shell_verified=True,
            scope_digest="a" * 64,
            evidence_digest="b" * 64,
        )
    return shared_mailbox_context.SharedMailboxContext(
        state=shared_mailbox_context.SharedMailboxContextState.UNVERIFIED,
        primary_context_verified=True,
        shared_shell_verified=False,
    )


def test_discovery_returns_only_verified_identity_free_candidates() -> None:
    candidates = (
        shared_mailbox_discovery.SyntheticSharedMailboxCandidate(
            "shared-ops",
            _context(valid=True),
        ),
        shared_mailbox_discovery.SyntheticSharedMailboxCandidate(
            "shared-unverified",
            _context(valid=False),
        ),
    )
    result = shared_mailbox_discovery.discover_shared_mailboxes(candidates)
    assert result.mailbox_keys == ("shared-ops",)
    opened = shared_mailbox_discovery.open_shared_mailbox(candidates, "shared-ops")
    assert opened.scope_verified is True
    assert opened.evidence_verified is True


def test_open_fails_closed_for_unverified_or_address_shaped_key() -> None:
    candidates = (
        shared_mailbox_discovery.SyntheticSharedMailboxCandidate(
            "shared-unverified",
            _context(valid=False),
        ),
    )
    with pytest.raises(ValueError, match="verified synthetic shared mailbox not found"):
        shared_mailbox_discovery.open_shared_mailbox(candidates, "shared-unverified")
    with pytest.raises(ValueError, match="opaque semantic token"):
        shared_mailbox_discovery.SyntheticSharedMailboxCandidate(
            "shared@example.invalid",
            _context(valid=True),
        )


def test_out111_remains_reserved_and_not_public() -> None:
    outlook = default_application_registry().get(ApplicationKey.OUTLOOK)
    assert outlook.state is ApplicationState.RESERVED
    assert default_tool_registry().by_application("outlook") == ()
