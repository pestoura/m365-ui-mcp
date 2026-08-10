"""Shared-mailbox-scoped synthetic search/read semantics for OUT-112."""

from __future__ import annotations

from dataclasses import dataclass

from m365_mcp.apps.outlook.mail_search import (
    MailSearchRequest,
    MailSearchResult,
    search_fixture_messages,
)
from m365_mcp.apps.outlook.message_get import (
    MessageGetRequest,
    MessageGetResult,
    get_fixture_message,
)
from m365_mcp.apps.outlook.mock_ui import OutlookMockFixture
from m365_mcp.apps.outlook.readiness import OutlookReadinessReport
from m365_mcp.apps.outlook.shared_mailbox_context import SharedMailboxContext


@dataclass(frozen=True)
class SharedMailboxSearchResult:
    result: MailSearchResult
    shared_scope_verified: bool
    synthetic: bool = True


@dataclass(frozen=True)
class SharedMailboxMessageResult:
    result: MessageGetResult
    shared_scope_verified: bool
    synthetic: bool = True


def _gate(context: SharedMailboxContext) -> None:
    if not context.valid:
        raise ValueError("verified shared mailbox context is required")


def search_shared_mailbox_messages(
    context: SharedMailboxContext,
    fixture: OutlookMockFixture,
    request: MailSearchRequest,
    *,
    readiness: OutlookReadinessReport,
) -> SharedMailboxSearchResult:
    """Run existing bounded mail search only inside a verified shared scope."""
    _gate(context)
    result = search_fixture_messages(fixture, request, readiness=readiness)
    return SharedMailboxSearchResult(result=result, shared_scope_verified=True)


def get_shared_mailbox_message(
    context: SharedMailboxContext,
    fixture: OutlookMockFixture,
    request: MessageGetRequest,
    *,
    readiness: OutlookReadinessReport,
) -> SharedMailboxMessageResult:
    """Run existing bounded message get only inside a verified shared scope."""
    _gate(context)
    result = get_fixture_message(fixture, request, readiness=readiness)
    return SharedMailboxMessageResult(result=result, shared_scope_verified=True)


__all__ = [
    "SharedMailboxMessageResult",
    "SharedMailboxSearchResult",
    "get_shared_mailbox_message",
    "search_shared_mailbox_messages",
]
