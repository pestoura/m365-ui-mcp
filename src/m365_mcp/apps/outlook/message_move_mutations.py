"""Synthetic-only Outlook message move semantics for OUT-038."""

from __future__ import annotations

from dataclasses import dataclass, replace

from m365_mcp.apps.outlook.mock_ui import OutlookMockFixture
from m365_mcp.apps.outlook.readiness import OutlookReadinessReport


@dataclass(frozen=True)
class MessageMoveRequest:
    message_key: str
    target_folder_key: str

    def __post_init__(self) -> None:
        for name in ("message_key", "target_folder_key"):
            value = getattr(self, name)
            if not value or value != value.strip() or any(char.isspace() for char in value):
                raise ValueError(f"{name} must be a non-empty semantic token")

    def to_payload(self) -> dict[str, object]:
        return {
            "message_key": self.message_key,
            "target_folder_key": self.target_folder_key,
        }


@dataclass(frozen=True)
class MessageMoveResult:
    message_key: str
    previous_folder_key: str
    requested_folder_key: str
    read_back_folder_key: str
    changed: bool
    verified: bool
    synthetic: bool = True

    def to_projection(self) -> dict[str, object]:
        return {
            "message_key": self.message_key,
            "previous_folder_key": self.previous_folder_key,
            "requested_folder_key": self.requested_folder_key,
            "read_back_folder_key": self.read_back_folder_key,
            "changed": self.changed,
            "verified": self.verified,
            "synthetic": self.synthetic,
        }


def apply_fixture_message_move(
    fixture: OutlookMockFixture,
    request: MessageMoveRequest,
    *,
    readiness: OutlookReadinessReport,
) -> tuple[OutlookMockFixture, MessageMoveResult]:
    """Move one synthetic message and immediately prove the destination."""
    if not fixture.synthetic:
        raise ValueError("OUT-038 fixture execution requires synthetic=true")
    if not readiness.ready_for_readonly_discovery:
        raise ValueError("Outlook read-only discovery is not ready")
    if request.target_folder_key not in fixture.folders:
        raise ValueError("target folder does not exist in synthetic fixture")

    current = next(
        (message for message in fixture.messages if message.message_key == request.message_key),
        None,
    )
    if current is None:
        raise ValueError("synthetic message_key not found")

    updated_message = replace(current, folder_key=request.target_folder_key)
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
    if read_back.folder_key != request.target_folder_key:
        raise RuntimeError("synthetic read-back did not prove requested message move")

    return updated_fixture, MessageMoveResult(
        message_key=request.message_key,
        previous_folder_key=current.folder_key,
        requested_folder_key=request.target_folder_key,
        read_back_folder_key=read_back.folder_key,
        changed=current.folder_key != request.target_folder_key,
        verified=True,
    )


__all__ = ["MessageMoveRequest", "MessageMoveResult", "apply_fixture_message_move"]
