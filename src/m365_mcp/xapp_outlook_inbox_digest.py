"""Synthetic-only Outlook inbox digest composite for XAPP-020.

The digest reduces an already-produced bounded message-list result to counts and
opaque message keys. It never reads a mailbox, exposes message content, or
promotes Outlook live/public support.
"""

from __future__ import annotations

from dataclasses import dataclass

from m365_mcp.apps.outlook.message_list import MessageListResult

_MAX_ATTENTION_KEYS = 100


@dataclass(frozen=True)
class OutlookInboxDigest:
    page_count: int
    total_matching: int
    unread_count: int
    attachment_count: int
    attention_message_keys: tuple[str, ...]
    synthetic: bool = True
    live_observed: bool = False
    execution_performed: bool = False

    def __post_init__(self) -> None:
        if not self.synthetic:
            raise ValueError("Outlook inbox digest must remain synthetic")
        if self.live_observed:
            raise ValueError("Outlook inbox digest must not claim live observation")
        if self.execution_performed:
            raise ValueError("Outlook inbox digest must not execute mailbox operations")
        if len(self.attention_message_keys) > _MAX_ATTENTION_KEYS:
            raise ValueError("attention message keys exceed bounded size")
        if len(self.attention_message_keys) != len(set(self.attention_message_keys)):
            raise ValueError("attention message keys must be unique")


def build_synthetic_inbox_digest(
    result: MessageListResult,
    *,
    max_attention_keys: int = 20,
) -> OutlookInboxDigest:
    """Reduce one synthetic inbox page to identity-free counters and opaque keys."""
    if not result.synthetic:
        raise ValueError("XAPP-020 requires a synthetic Outlook message-list result")
    if result.folder_key != "inbox":
        raise ValueError("XAPP-020 requires the synthetic inbox folder")
    if not 1 <= max_attention_keys <= _MAX_ATTENTION_KEYS:
        raise ValueError("max_attention_keys must be between 1 and 100")
    if any(item.folder_key != "inbox" for item in result.items):
        raise ValueError("inbox digest contains an item from another folder")

    unread_keys = tuple(sorted(item.message_key for item in result.items if not item.is_read))
    return OutlookInboxDigest(
        page_count=len(result.items),
        total_matching=result.total_matching,
        unread_count=len(unread_keys),
        attachment_count=sum(item.has_attachments for item in result.items),
        attention_message_keys=unread_keys[:max_attention_keys],
    )


__all__ = ["OutlookInboxDigest", "build_synthetic_inbox_digest"]
