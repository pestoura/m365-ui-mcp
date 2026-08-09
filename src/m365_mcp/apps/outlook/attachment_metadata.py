"""Synthetic-only Outlook attachment metadata/list semantics for OUT-014.

No attachment bytes, storage locator, URL or download primitive is exposed.
Controlled retrieval is intentionally reserved for OUT-015.
"""

from __future__ import annotations

from dataclasses import dataclass

from m365_mcp.apps.outlook.mock_ui import OutlookMockFixture
from m365_mcp.apps.outlook.readiness import OutlookReadinessReport


@dataclass(frozen=True)
class SyntheticAttachment:
    """Tenant-neutral attachment metadata bound to one synthetic message."""

    attachment_key: str
    message_key: str
    file_name: str
    media_type: str
    size_bytes: int

    def __post_init__(self) -> None:
        for field_name in ("attachment_key", "message_key"):
            value = getattr(self, field_name)
            invalid = (
                not value
                or value != value.strip()
                or any(char.isspace() for char in value)
            )
            if invalid:
                raise ValueError(f"{field_name} must be a non-empty semantic token")
        if not self.file_name or self.file_name != self.file_name.strip():
            raise ValueError("file_name must be non-empty")
        if "/" not in self.media_type or any(char.isspace() for char in self.media_type):
            raise ValueError("media_type must be a valid type/subtype token")
        if self.size_bytes < 0:
            raise ValueError("size_bytes must be non-negative")


@dataclass(frozen=True)
class AttachmentMetadataResult:
    """Bounded metadata list for one synthetic message."""

    message_key: str
    attachments: tuple[SyntheticAttachment, ...]
    attachment_count: int
    synthetic: bool


def default_synthetic_attachments() -> tuple[SyntheticAttachment, ...]:
    """Return explicit synthetic attachment metadata without payload content."""
    return (
        SyntheticAttachment(
            attachment_key="att-001",
            message_key="msg-002",
            file_name="synthetic-meeting-notes.txt",
            media_type="text/plain",
            size_bytes=128,
        ),
    )


def list_fixture_attachment_metadata(
    fixture: OutlookMockFixture,
    message_key: str,
    *,
    readiness: OutlookReadinessReport,
    attachments: tuple[SyntheticAttachment, ...] | None = None,
) -> AttachmentMetadataResult:
    """List metadata only for one existing synthetic message."""
    if not fixture.synthetic:
        raise ValueError("OUT-014 fixture execution requires synthetic=true")
    if not readiness.ready_for_readonly_discovery:
        raise ValueError("Outlook read-only discovery is not ready")
    if not message_key or message_key != message_key.strip():
        raise ValueError("message_key must be a non-empty semantic token")

    message = next((item for item in fixture.messages if item.message_key == message_key), None)
    if message is None:
        raise ValueError("synthetic message_key not found")

    catalog = default_synthetic_attachments() if attachments is None else attachments
    attachment_keys = tuple(item.attachment_key for item in catalog)
    if len(set(attachment_keys)) != len(attachment_keys):
        raise ValueError("attachment catalog keys must be unique")
    dangling = tuple(
        item.message_key
        for item in catalog
        if not any(message.message_key == item.message_key for message in fixture.messages)
    )
    if dangling:
        raise ValueError("attachment catalog references unknown synthetic message_key")

    selected = tuple(item for item in catalog if item.message_key == message_key)
    if bool(selected) != message.has_attachments:
        raise ValueError("attachment metadata disagrees with message attachment state")

    return AttachmentMetadataResult(
        message_key=message_key,
        attachments=selected,
        attachment_count=len(selected),
        synthetic=True,
    )


__all__ = [
    "AttachmentMetadataResult",
    "SyntheticAttachment",
    "default_synthetic_attachments",
    "list_fixture_attachment_metadata",
]
