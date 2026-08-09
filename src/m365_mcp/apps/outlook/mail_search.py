"""Bounded synthetic Outlook mail search semantics for OUT-012.

This is a semantic filter over the OUT-002 fixture, not a generic browser or
query primitive. Live execution remains unavailable until separately attested.
"""

from __future__ import annotations

from dataclasses import dataclass

from m365_mcp.apps.outlook.message_list import MessageListItem
from m365_mcp.apps.outlook.mock_ui import OutlookMockFixture
from m365_mcp.apps.outlook.readiness import OutlookReadinessReport

_MAX_PAGE_SIZE = 100
_MAX_QUERY_LENGTH = 200


@dataclass(frozen=True)
class MailSearchRequest:
    """Closed bounded search request over reviewed message metadata."""

    query: str | None = None
    folder_key: str | None = None
    is_read: bool | None = None
    has_attachments: bool | None = None
    offset: int = 0
    limit: int = 50

    def __post_init__(self) -> None:
        if self.query is not None:
            normalized = self.query.strip()
            if not normalized:
                raise ValueError("query must not be empty when supplied")
            if len(normalized) > _MAX_QUERY_LENGTH:
                raise ValueError(f"query must be at most {_MAX_QUERY_LENGTH} characters")
        if self.folder_key is not None:
            if not self.folder_key or self.folder_key != self.folder_key.strip():
                raise ValueError("folder_key must be a non-empty semantic token")
            if any(char.isspace() for char in self.folder_key):
                raise ValueError("folder_key must not contain whitespace")
        if self.offset < 0:
            raise ValueError("offset must be non-negative")
        if not 1 <= self.limit <= _MAX_PAGE_SIZE:
            raise ValueError(f"limit must be between 1 and {_MAX_PAGE_SIZE}")


@dataclass(frozen=True)
class MailSearchResult:
    """Deterministic synthetic search result page."""

    items: tuple[MessageListItem, ...]
    offset: int
    limit: int
    total_matching: int
    has_more: bool
    synthetic: bool


def search_fixture_messages(
    fixture: OutlookMockFixture,
    request: MailSearchRequest,
    *,
    readiness: OutlookReadinessReport,
) -> MailSearchResult:
    """Search reviewed synthetic metadata only when read discovery is ready."""
    if not fixture.synthetic:
        raise ValueError("OUT-012 fixture execution requires synthetic=true")
    if not readiness.ready_for_readonly_discovery:
        raise ValueError("Outlook read-only discovery is not ready")
    if request.folder_key is not None and request.folder_key not in fixture.folders:
        raise ValueError("unknown synthetic folder_key")

    query = request.query.strip().casefold() if request.query is not None else None
    matching = tuple(
        message
        for message in fixture.messages
        if (query is None or query in message.subject.casefold())
        and (request.folder_key is None or message.folder_key == request.folder_key)
        and (request.is_read is None or message.is_read is request.is_read)
        and (
            request.has_attachments is None
            or message.has_attachments is request.has_attachments
        )
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
    return MailSearchResult(
        items=items,
        offset=request.offset,
        limit=request.limit,
        total_matching=len(matching),
        has_more=end < len(matching),
        synthetic=True,
    )


__all__ = ["MailSearchRequest", "MailSearchResult", "search_fixture_messages"]
