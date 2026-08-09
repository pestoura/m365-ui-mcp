"""Bounded Outlook message-list semantics for OUT-010.

The first implementation is deliberately source-neutral and exercised only
against the synthetic OUT-002 fixture. Live/browser execution remains gated by
OUT-007 readiness plus later UI-contract evidence and worker adaptation.
"""

from __future__ import annotations

from dataclasses import dataclass

from m365_mcp.apps.outlook.mock_ui import OutlookMockFixture
from m365_mcp.apps.outlook.readiness import OutlookReadinessReport

_MAX_PAGE_SIZE = 100


@dataclass(frozen=True)
class MessageListRequest:
    """Bounded, identity-free message-list request."""

    folder_key: str = "inbox"
    offset: int = 0
    limit: int = 50

    def __post_init__(self) -> None:
        if not self.folder_key or self.folder_key != self.folder_key.strip():
            raise ValueError("folder_key must be a non-empty semantic token")
        if any(char.isspace() for char in self.folder_key):
            raise ValueError("folder_key must not contain whitespace")
        if self.offset < 0:
            raise ValueError("offset must be non-negative")
        if not 1 <= self.limit <= _MAX_PAGE_SIZE:
            raise ValueError(f"limit must be between 1 and {_MAX_PAGE_SIZE}")


@dataclass(frozen=True)
class MessageListItem:
    """Minimal read-only message metadata returned by OUT-010."""

    message_key: str
    subject: str
    folder_key: str
    is_read: bool
    has_attachments: bool


@dataclass(frozen=True)
class MessageListResult:
    """Deterministic bounded page of message-list metadata."""

    items: tuple[MessageListItem, ...]
    folder_key: str
    offset: int
    limit: int
    total_matching: int
    has_more: bool
    synthetic: bool


def list_fixture_messages(
    fixture: OutlookMockFixture,
    request: MessageListRequest,
    *,
    readiness: OutlookReadinessReport,
) -> MessageListResult:
    """List synthetic message metadata only when read discovery is ready."""
    if not fixture.synthetic:
        raise ValueError("OUT-010 fixture execution requires synthetic=true")
    if not readiness.ready_for_readonly_discovery:
        raise ValueError("Outlook read-only discovery is not ready")
    if request.folder_key not in fixture.folders:
        raise ValueError("unknown synthetic folder_key")

    matching = tuple(
        message for message in fixture.messages if message.folder_key == request.folder_key
    )
    page = matching[request.offset : request.offset + request.limit]
    items = tuple(
        MessageListItem(
            message_key=message.message_key,
            subject=message.subject,
            folder_key=message.folder_key,
            is_read=message.is_read,
            has_attachments=message.has_attachments,
        )
        for message in page
    )
    end = request.offset + len(items)
    return MessageListResult(
        items=items,
        folder_key=request.folder_key,
        offset=request.offset,
        limit=request.limit,
        total_matching=len(matching),
        has_more=end < len(matching),
        synthetic=True,
    )


__all__ = [
    "MessageListItem",
    "MessageListRequest",
    "MessageListResult",
    "list_fixture_messages",
]
