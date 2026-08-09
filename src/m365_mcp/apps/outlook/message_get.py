"""Synthetic-only Outlook message get/read semantics for OUT-011."""

from __future__ import annotations

from dataclasses import dataclass

from m365_mcp.apps.outlook.mock_ui import OutlookMockFixture
from m365_mcp.apps.outlook.readiness import OutlookReadinessReport


@dataclass(frozen=True)
class MessageGetRequest:
    """Opaque semantic request for one message."""

    message_key: str

    def __post_init__(self) -> None:
        if not self.message_key or self.message_key != self.message_key.strip():
            raise ValueError("message_key must be a non-empty semantic token")
        if any(char.isspace() for char in self.message_key):
            raise ValueError("message_key must not contain whitespace")


@dataclass(frozen=True)
class MessageGetResult:
    """Bounded message-read result supported by the synthetic fixture."""

    message_key: str
    subject: str
    folder_key: str
    is_read: bool
    has_attachments: bool
    synthetic: bool


def get_fixture_message(
    fixture: OutlookMockFixture,
    request: MessageGetRequest,
    *,
    readiness: OutlookReadinessReport,
) -> MessageGetResult:
    """Return one synthetic message only when read-only discovery is ready."""
    if not fixture.synthetic:
        raise ValueError("OUT-011 fixture execution requires synthetic=true")
    if not readiness.ready_for_readonly_discovery:
        raise ValueError("Outlook read-only discovery is not ready")

    message = next(
        (item for item in fixture.messages if item.message_key == request.message_key),
        None,
    )
    if message is None:
        raise ValueError("synthetic message_key not found")

    return MessageGetResult(
        message_key=message.message_key,
        subject=message.subject,
        folder_key=message.folder_key,
        is_read=message.is_read,
        has_attachments=message.has_attachments,
        synthetic=True,
    )


__all__ = ["MessageGetRequest", "MessageGetResult", "get_fixture_message"]
