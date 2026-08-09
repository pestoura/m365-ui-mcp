"""Synthetic-only Outlook mark read/unread semantics for OUT-030.

This module mutates only the immutable OUT-002 synthetic fixture. It is not a
public tool and does not execute browser operations. Public Outlook mutations
remain denied while the application is RESERVED; live execution must later use
the canonical policy, approval, idempotency, lock, lifecycle and read-back path.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

from m365_mcp.apps.outlook.mock_ui import OutlookMockFixture
from m365_mcp.apps.outlook.readiness import OutlookReadinessReport


@dataclass(frozen=True)
class MessageReadMutationRequest:
    """Desired read state for one synthetic message."""

    message_key: str
    is_read: bool

    def __post_init__(self) -> None:
        invalid_key = (
            not self.message_key
            or self.message_key != self.message_key.strip()
            or any(char.isspace() for char in self.message_key)
        )
        if invalid_key:
            raise ValueError("message_key must be a non-empty semantic token")
        if not isinstance(self.is_read, bool):
            raise ValueError("is_read must be a boolean")

    def to_payload(self) -> dict[str, object]:
        """Return bounded semantic request data suitable for idempotency hashing."""
        return {"message_key": self.message_key, "is_read": self.is_read}


@dataclass(frozen=True)
class MessageReadMutationResult:
    """Verified synthetic read-back for one mark read/unread operation."""

    message_key: str
    requested_is_read: bool
    previous_is_read: bool
    read_back_is_read: bool
    changed: bool
    verified: bool
    synthetic: bool = True

    def to_projection(self) -> dict[str, object]:
        return {
            "message_key": self.message_key,
            "requested_is_read": self.requested_is_read,
            "previous_is_read": self.previous_is_read,
            "read_back_is_read": self.read_back_is_read,
            "changed": self.changed,
            "verified": self.verified,
            "synthetic": self.synthetic,
        }


def apply_fixture_message_read_state(
    fixture: OutlookMockFixture,
    request: MessageReadMutationRequest,
    *,
    readiness: OutlookReadinessReport,
) -> tuple[OutlookMockFixture, MessageReadMutationResult]:
    """Apply and immediately read back one mutation against the synthetic fixture."""
    if not fixture.synthetic:
        raise ValueError("OUT-030 fixture execution requires synthetic=true")
    if not readiness.ready_for_readonly_discovery:
        raise ValueError("Outlook read-only discovery is not ready")

    current = next(
        (message for message in fixture.messages if message.message_key == request.message_key),
        None,
    )
    if current is None:
        raise ValueError("synthetic message_key not found")

    updated_message = replace(current, is_read=request.is_read)
    updated_fixture = replace(
        fixture,
        messages=tuple(
            updated_message if message.message_key == request.message_key else message
            for message in fixture.messages
        ),
    )
    read_back = next(
        message
        for message in updated_fixture.messages
        if message.message_key == request.message_key
    )
    verified = read_back.is_read is request.is_read
    if not verified:
        raise RuntimeError("synthetic read-back did not prove requested read state")

    return (
        updated_fixture,
        MessageReadMutationResult(
            message_key=request.message_key,
            requested_is_read=request.is_read,
            previous_is_read=current.is_read,
            read_back_is_read=read_back.is_read,
            changed=current.is_read is not request.is_read,
            verified=True,
        ),
    )


__all__ = [
    "MessageReadMutationRequest",
    "MessageReadMutationResult",
    "apply_fixture_message_read_state",
]
