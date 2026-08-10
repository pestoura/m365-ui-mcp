from __future__ import annotations

import pytest

from m365_mcp.application_registry import (
    ApplicationKey,
    ApplicationState,
    default_application_registry,
)
from m365_mcp.apps.outlook import (
    shared_calendar_linkage,
    shared_calendar_reads,
    shared_mailbox_context,
)
from m365_mcp.tool_registry import default_tool_registry


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


def test_shared_calendar_linkage_is_opaque_and_permission_scoped() -> None:
    scopes = (
        shared_calendar_reads.SharedCalendarScope(
            "scope-team",
            "cal-team",
            shared_calendar_reads.SharedCalendarPermission.LIMITED_DETAILS,
        ),
    )
    result = shared_calendar_linkage.resolve_shared_calendar_linkage(
        _context(),
        "scope-team",
        scopes=scopes,
    )
    assert result.linkage_key.startswith("link-")
    assert result.permission is shared_calendar_reads.SharedCalendarPermission.LIMITED_DETAILS
    assert "@" not in result.linkage_key
    assert result.verified is True


def test_shared_calendar_linkage_fails_closed_without_scope_or_permission() -> None:
    scopes = (
        shared_calendar_reads.SharedCalendarScope(
            "scope-none",
            "cal-team",
            shared_calendar_reads.SharedCalendarPermission.NONE,
        ),
    )
    with pytest.raises(ValueError, match="verified shared mailbox context"):
        shared_calendar_linkage.resolve_shared_calendar_linkage(
            _context(False),
            "scope-none",
            scopes=scopes,
        )
    with pytest.raises(ValueError, match="no delegated permission"):
        shared_calendar_linkage.resolve_shared_calendar_linkage(
            _context(),
            "scope-none",
            scopes=scopes,
        )


def test_out118_remains_reserved_and_not_public() -> None:
    outlook = default_application_registry().get(ApplicationKey.OUTLOOK)
    assert outlook.state is ApplicationState.RESERVED
    assert default_tool_registry().by_application("outlook") == ()
