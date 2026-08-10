from __future__ import annotations

import pytest

from m365_mcp.application_registry import (
    ApplicationKey,
    ApplicationState,
    default_application_registry,
)
from m365_mcp.apps.outlook import shared_mailbox_auto_replies, shared_mailbox_context
from m365_mcp.tool_registry import default_tool_registry


def _context(*, valid: bool) -> shared_mailbox_context.SharedMailboxContext:
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


def test_auto_reply_settings_set_disable_and_never_dispatch() -> None:
    current = shared_mailbox_auto_replies.SharedMailboxAutoReplySettings(enabled=False)
    current, enabled = shared_mailbox_auto_replies.mutate_shared_mailbox_auto_replies(
        _context(valid=True),
        current,
        shared_mailbox_auto_replies.AutoReplyRequest(
            shared_mailbox_auto_replies.AutoReplyAction.SET,
            internal_message="Synthetic internal reply",
            external_message="Synthetic external reply",
        ),
    )
    assert enabled.read_back.enabled is True
    assert enabled.dispatched is False
    _, repeated = shared_mailbox_auto_replies.mutate_shared_mailbox_auto_replies(
        _context(valid=True),
        current,
        shared_mailbox_auto_replies.AutoReplyRequest(
            shared_mailbox_auto_replies.AutoReplyAction.SET,
            internal_message="Synthetic internal reply",
            external_message="Synthetic external reply",
        ),
    )
    assert repeated.changed is False
    disabled, result = shared_mailbox_auto_replies.mutate_shared_mailbox_auto_replies(
        _context(valid=True),
        current,
        shared_mailbox_auto_replies.AutoReplyRequest(
            shared_mailbox_auto_replies.AutoReplyAction.DISABLE,
        ),
    )
    assert disabled.enabled is False
    assert result.dispatched is False


def test_auto_reply_settings_fail_closed_without_verified_scope() -> None:
    with pytest.raises(ValueError, match="verified shared mailbox context"):
        shared_mailbox_auto_replies.mutate_shared_mailbox_auto_replies(
            _context(valid=False),
            shared_mailbox_auto_replies.SharedMailboxAutoReplySettings(enabled=False),
            shared_mailbox_auto_replies.AutoReplyRequest(
                shared_mailbox_auto_replies.AutoReplyAction.SET,
                internal_message="Synthetic reply",
            ),
        )


def test_out115_remains_reserved_and_not_public() -> None:
    outlook = default_application_registry().get(ApplicationKey.OUTLOOK)
    assert outlook.state is ApplicationState.RESERVED
    assert default_tool_registry().by_application("outlook") == ()
