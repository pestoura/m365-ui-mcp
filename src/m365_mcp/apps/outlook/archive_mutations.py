"""Synthetic-only Outlook archive/restore semantics for OUT-037."""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import StrEnum

from m365_mcp.apps.outlook.mock_ui import OutlookMockFixture
from m365_mcp.apps.outlook.readiness import OutlookReadinessReport

_ARCHIVE_FOLDER = "archive"


class ArchiveMutationAction(StrEnum):
    ARCHIVE = "ARCHIVE"
    RESTORE = "RESTORE"


@dataclass(frozen=True)
class ArchiveMutationRequest:
    action: ArchiveMutationAction
    message_key: str
    restore_folder_key: str | None = None

    def __post_init__(self) -> None:
        for name in ("message_key", "restore_folder_key"):
            value = getattr(self, name)
            if value is None:
                continue
            if not value or value != value.strip() or any(char.isspace() for char in value):
                raise ValueError(f"{name} must be a non-empty semantic token")
        if self.action is ArchiveMutationAction.ARCHIVE and self.restore_folder_key is not None:
            raise ValueError("archive must not provide restore_folder_key")
        if self.action is ArchiveMutationAction.RESTORE:
            if self.restore_folder_key is None:
                raise ValueError("restore requires explicit restore_folder_key")
            if self.restore_folder_key == _ARCHIVE_FOLDER:
                raise ValueError("restore target must not be archive")

    def to_payload(self) -> dict[str, object]:
        return {
            "action": self.action.value,
            "message_key": self.message_key,
            "restore_folder_key": self.restore_folder_key,
        }


@dataclass(frozen=True)
class ArchiveMutationResult:
    action: ArchiveMutationAction
    message_key: str
    previous_folder_key: str
    read_back_folder_key: str
    changed: bool
    verified: bool
    synthetic: bool = True

    def to_projection(self) -> dict[str, object]:
        return {
            "action": self.action.value,
            "message_key": self.message_key,
            "previous_folder_key": self.previous_folder_key,
            "read_back_folder_key": self.read_back_folder_key,
            "changed": self.changed,
            "verified": self.verified,
            "synthetic": self.synthetic,
        }


def apply_fixture_archive_mutation(
    fixture: OutlookMockFixture,
    request: ArchiveMutationRequest,
    *,
    readiness: OutlookReadinessReport,
) -> tuple[OutlookMockFixture, ArchiveMutationResult]:
    """Archive or explicitly restore one synthetic message with read-back."""
    if not fixture.synthetic:
        raise ValueError("OUT-037 fixture execution requires synthetic=true")
    if not readiness.ready_for_readonly_discovery:
        raise ValueError("Outlook read-only discovery is not ready")

    current = next(
        (message for message in fixture.messages if message.message_key == request.message_key),
        None,
    )
    if current is None:
        raise ValueError("synthetic message_key not found")

    if request.action is ArchiveMutationAction.ARCHIVE:
        target = _ARCHIVE_FOLDER
    else:
        if current.folder_key != _ARCHIVE_FOLDER and current.folder_key != request.restore_folder_key:
            raise ValueError("restore requires message to be archived")
        target = request.restore_folder_key
        if target is None:
            raise RuntimeError("validated restore target unexpectedly absent")

    if target not in fixture.folders:
        raise ValueError("target folder does not exist in synthetic fixture")

    updated_message = replace(current, folder_key=target)
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
    if read_back.folder_key != target:
        raise RuntimeError("synthetic read-back did not prove requested archive state")

    return updated_fixture, ArchiveMutationResult(
        action=request.action,
        message_key=request.message_key,
        previous_folder_key=current.folder_key,
        read_back_folder_key=read_back.folder_key,
        changed=current.folder_key != target,
        verified=True,
    )


__all__ = [
    "ArchiveMutationAction",
    "ArchiveMutationRequest",
    "ArchiveMutationResult",
    "apply_fixture_archive_mutation",
]
