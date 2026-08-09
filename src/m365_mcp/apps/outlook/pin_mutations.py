"""Synthetic-only Outlook pin/unpin semantics for OUT-035.

The operation changes only tenant-neutral PinSnoozeMarker tuples and verifies
the requested state through OUT-019 reads. Pinning a snoozed message is refused
until OUT-036 unsnooze semantics are applied, preventing an implicit transition.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from m365_mcp.apps.outlook.mock_ui import OutlookMockFixture
from m365_mcp.apps.outlook.pin_snooze_reads import (
    PinSnoozeMarker,
    SnoozeState,
    read_fixture_pin_snooze_state,
)
from m365_mcp.apps.outlook.readiness import OutlookReadinessReport


class PinMutationAction(StrEnum):
    PIN = "PIN"
    UNPIN = "UNPIN"


@dataclass(frozen=True)
class PinMutationRequest:
    action: PinMutationAction
    message_key: str

    def __post_init__(self) -> None:
        if not isinstance(self.action, PinMutationAction):
            raise ValueError("action must be a closed PinMutationAction")
        invalid_key = (
            not self.message_key
            or self.message_key != self.message_key.strip()
            or any(char.isspace() for char in self.message_key)
        )
        if invalid_key:
            raise ValueError("message_key must be a non-empty semantic token")

    def to_payload(self) -> dict[str, str]:
        return {
            "action": self.action.value,
            "message_key": self.message_key,
        }


@dataclass(frozen=True)
class PinMutationResult:
    action: PinMutationAction
    message_key: str
    previous_is_pinned: bool
    read_back_is_pinned: bool
    changed: bool
    verified: bool
    synthetic: bool = True


def _current_marker(
    markers: tuple[PinSnoozeMarker, ...],
    message_key: str,
) -> PinSnoozeMarker | None:
    return next((item for item in markers if item.message_key == message_key), None)


def apply_fixture_pin_mutation(
    fixture: OutlookMockFixture,
    request: PinMutationRequest,
    *,
    readiness: OutlookReadinessReport,
    markers: tuple[PinSnoozeMarker, ...],
) -> tuple[tuple[PinSnoozeMarker, ...], PinMutationResult]:
    """Apply a synthetic pin transition and verify it through OUT-019."""
    if not fixture.synthetic:
        raise ValueError("OUT-035 fixture execution requires synthetic=true")
    if not readiness.ready_for_readonly_discovery:
        raise ValueError("Outlook read-only discovery is not ready")
    if not any(message.message_key == request.message_key for message in fixture.messages):
        raise ValueError("synthetic message_key not found")

    current = _current_marker(markers, request.message_key)
    previous = current.is_pinned if current is not None else False

    if request.action is PinMutationAction.PIN:
        if current is not None and current.snooze_state is SnoozeState.SNOOZED:
            raise ValueError("snoozed message must be unsnoozed before pinning")
        replacement = PinSnoozeMarker(
            message_key=request.message_key,
            is_pinned=True,
        )
        changed = current != replacement
        updated = tuple(
            item for item in markers if item.message_key != request.message_key
        ) + (replacement,)
    else:
        if current is None:
            updated = markers
            changed = False
        elif current.snooze_state is SnoozeState.SNOOZED:
            updated = markers
            changed = False
        else:
            updated = tuple(
                item for item in markers if item.message_key != request.message_key
            )
            changed = current.is_pinned

    read_back = read_fixture_pin_snooze_state(
        fixture,
        request.message_key,
        readiness=readiness,
        markers=updated,
    )
    expected = request.action is PinMutationAction.PIN
    if read_back.is_pinned is not expected:
        raise RuntimeError("synthetic pin read-back did not prove requested state")

    return (
        updated,
        PinMutationResult(
            action=request.action,
            message_key=request.message_key,
            previous_is_pinned=previous,
            read_back_is_pinned=read_back.is_pinned,
            changed=changed,
            verified=True,
        ),
    )


__all__ = [
    "PinMutationAction",
    "PinMutationRequest",
    "PinMutationResult",
    "apply_fixture_pin_mutation",
]
