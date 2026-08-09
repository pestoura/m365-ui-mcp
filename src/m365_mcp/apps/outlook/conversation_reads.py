"""Synthetic-only Outlook conversation/thread reads for OUT-013.

Thread membership is explicit synthetic fixture metadata. The implementation
never infers conversations from subject text and exposes no generic search or
browser primitive.
"""

from __future__ import annotations

from dataclasses import dataclass

from m365_mcp.apps.outlook.message_list import MessageListItem
from m365_mcp.apps.outlook.mock_ui import OutlookMockFixture
from m365_mcp.apps.outlook.readiness import OutlookReadinessReport


@dataclass(frozen=True)
class SyntheticConversation:
    """Explicit tenant-neutral mapping from a synthetic thread to message keys."""

    conversation_key: str
    message_keys: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.conversation_key or self.conversation_key != self.conversation_key.strip():
            raise ValueError("conversation_key must be a non-empty semantic token")
        if any(char.isspace() for char in self.conversation_key):
            raise ValueError("conversation_key must not contain whitespace")
        if not self.message_keys or len(set(self.message_keys)) != len(self.message_keys):
            raise ValueError("conversation message_keys must be non-empty and unique")


@dataclass(frozen=True)
class ConversationReadResult:
    """Bounded synthetic conversation result in explicit fixture order."""

    conversation_key: str
    messages: tuple[MessageListItem, ...]
    message_count: int
    synthetic: bool


def default_synthetic_conversations() -> tuple[SyntheticConversation, ...]:
    """Return explicit synthetic thread membership without content inference."""
    return (
        SyntheticConversation("thread-project-update", ("msg-001",)),
        SyntheticConversation("thread-meeting-notes", ("msg-002",)),
    )


def read_fixture_conversation(
    fixture: OutlookMockFixture,
    conversation_key: str,
    *,
    readiness: OutlookReadinessReport,
    conversations: tuple[SyntheticConversation, ...] | None = None,
) -> ConversationReadResult:
    """Read one explicit synthetic conversation fail closed."""
    if not fixture.synthetic:
        raise ValueError("OUT-013 fixture execution requires synthetic=true")
    if not readiness.ready_for_readonly_discovery:
        raise ValueError("Outlook read-only discovery is not ready")
    if not conversation_key or conversation_key != conversation_key.strip():
        raise ValueError("conversation_key must be a non-empty semantic token")

    catalog = conversations or default_synthetic_conversations()
    keys = tuple(item.conversation_key for item in catalog)
    if len(set(keys)) != len(keys):
        raise ValueError("conversation catalog keys must be unique")
    selected = next((item for item in catalog if item.conversation_key == conversation_key), None)
    if selected is None:
        raise ValueError("synthetic conversation_key not found")

    by_key = {message.message_key: message for message in fixture.messages}
    missing = tuple(key for key in selected.message_keys if key not in by_key)
    if missing:
        raise ValueError("conversation references unknown synthetic message_key")

    messages = tuple(
        MessageListItem(
            message_key=by_key[key].message_key,
            subject=by_key[key].subject,
            folder_key=by_key[key].folder_key,
            is_read=by_key[key].is_read,
            has_attachments=by_key[key].has_attachments,
        )
        for key in selected.message_keys
    )
    return ConversationReadResult(
        conversation_key=selected.conversation_key,
        messages=messages,
        message_count=len(messages),
        synthetic=True,
    )


__all__ = [
    "ConversationReadResult",
    "SyntheticConversation",
    "default_synthetic_conversations",
    "read_fixture_conversation",
]
