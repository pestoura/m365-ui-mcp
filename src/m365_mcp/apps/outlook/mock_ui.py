"""Synthetic Outlook fixture foundation for OUT-002.

Fixtures are intentionally tenant-neutral and contain no selectors, URLs,
credentials, mailbox addresses or copied Microsoft content. They provide a
stable mock data vocabulary for later Outlook contract and adapter tests.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class MockMessage:
    """Synthetic message metadata safe for isolated tests."""

    message_key: str
    subject: str
    folder_key: str
    is_read: bool
    has_attachments: bool = False


@dataclass(frozen=True)
class OutlookMockFixture:
    """Versioned tenant-neutral fixture set."""

    fixture_version: str
    synthetic: bool
    mailbox_key: str
    folders: tuple[str, ...]
    messages: tuple[MockMessage, ...]


def default_outlook_fixture() -> OutlookMockFixture:
    """Return the deterministic OUT-002 fixture used by isolated tests."""
    return OutlookMockFixture(
        fixture_version="outlook-mock-v1",
        synthetic=True,
        mailbox_key="mock-primary",
        folders=("inbox", "archive", "sent"),
        messages=(
            MockMessage(
                message_key="msg-001",
                subject="Synthetic project update",
                folder_key="inbox",
                is_read=False,
            ),
            MockMessage(
                message_key="msg-002",
                subject="Synthetic meeting notes",
                folder_key="archive",
                is_read=True,
                has_attachments=True,
            ),
        ),
    )


__all__ = ["MockMessage", "OutlookMockFixture", "default_outlook_fixture"]
