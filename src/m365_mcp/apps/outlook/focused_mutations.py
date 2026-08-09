"""Synthetic-only Outlook Focused/Other movement semantics for OUT-040."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from m365_mcp.apps.outlook.mock_ui import OutlookMockFixture
from m365_mcp.apps.outlook.readiness import OutlookReadinessReport

_INBOX_FOLDER = "inbox"


class FocusedInboxClass(StrEnum):
    FOCUSED = "FOCUSED"
    OTHER = "OTHER"


class FocusedMutationAction(StrEnum):
    MOVE_TO_FOCUSED = "MOVE_TO_FOCUSED"
    MOVE_TO_OTHER = "MOVE_TO_OTHER"

    @property
    def target_class(self) -> FocusedInboxClass:
        if self is FocusedMutationAction.MOVE_TO_FOCUSED:
            return FocusedInboxClass.FOCUSED
        return FocusedInboxClass.OTHER


@dataclass(frozen=True)
class FocusedInboxMarker:
    message_key: str
    classification: FocusedInboxClass

    def __post_init__(self) -> None:
        invalid_key = (
            not self.message_key
            or self.message_key != self.message_key.strip()
            or any(char.isspace() for char in self.message_key)
        )
        if invalid_key:
            raise ValueError("message_key must be a non-empty semantic token")


@dataclass(frozen=True)
class FocusedMutationRequest:
    action: FocusedMutationAction
    message_key: str

    def __post_init__(self) -> None:
        invalid_key = (
            not self.message_key
            or self.message_key != self.message_key.strip()
            or any(char.isspace() for char in self.message_key)
        )
        if invalid_key:
            raise ValueError("message_key must be a non-empty semantic token")

    def to_payload(self) -> dict[str, object]:
        return {"action": self.action.value, "message_key": self.message_key}


@dataclass(frozen=True)
class FocusedMutationResult:
    action: FocusedMutationAction
    message_key: str
    previous_class: FocusedInboxClass | None
    read_back_class: FocusedInboxClass
    changed: bool
    verified: bool
    synthetic: bool = True


def apply_fixture_focused_mutation(
    fixture: OutlookMockFixture,
    request: FocusedMutationRequest,
    *,
    readiness: OutlookReadinessReport,
    markers: tuple[FocusedInboxMarker, ...] = (),
) -> tuple[tuple[FocusedInboxMarker, ...], FocusedMutationResult]:
    """Move one Inbox message between synthetic Focused/Other classes."""
    if not fixture.synthetic:
        raise ValueError("OUT-040 fixture execution requires synthetic=true")
    if not readiness.ready_for_readonly_discovery:
        raise ValueError("Outlook read-only discovery is not ready")

    message = next(
        (item for item in fixture.messages if item.message_key == request.message_key),
        None,
    )
    if message is None:
        raise ValueError("synthetic message_key not found")
    if message.folder_key != _INBOX_FOLDER:
        raise ValueError("Focused/Other movement requires an Inbox message")

    by_message: dict[str, FocusedInboxMarker] = {}
    known_messages = {item.message_key for item in fixture.messages}
    for marker in markers:
        if marker.message_key in by_message:
            raise ValueError("duplicate Focused/Other marker")
        if marker.message_key not in known_messages:
            raise ValueError("Focused/Other marker references unknown message")
        by_message[marker.message_key] = marker

    current = by_message.get(request.message_key)
    previous_class = current.classification if current is not None else None
    target = request.action.target_class
    replacement = FocusedInboxMarker(request.message_key, target)
    if current is None:
        updated = markers + (replacement,)
    else:
        updated = tuple(
            replacement if marker.message_key == request.message_key else marker
            for marker in markers
        )

    read_back = next(
        marker for marker in updated if marker.message_key == request.message_key
    )
    if read_back.classification is not target:
        raise RuntimeError("synthetic read-back did not prove Focused/Other state")

    return updated, FocusedMutationResult(
        action=request.action,
        message_key=request.message_key,
        previous_class=previous_class,
        read_back_class=read_back.classification,
        changed=previous_class is not target,
        verified=True,
    )


__all__ = [
    "FocusedInboxClass",
    "FocusedInboxMarker",
    "FocusedMutationAction",
    "FocusedMutationRequest",
    "FocusedMutationResult",
    "apply_fixture_focused_mutation",
]
