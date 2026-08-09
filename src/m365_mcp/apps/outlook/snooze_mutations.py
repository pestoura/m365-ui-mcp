"""Synthetic-only Outlook snooze/unsnooze semantics for OUT-036.

The operation changes only tenant-neutral PinSnoozeMarker tuples and verifies
the result through OUT-019 reads. Snoozing a pinned message is refused rather
than silently unpinning it. Outlook remains RESERVED.
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

_MIN_DAY_OFFSET = -3650
_MAX_DAY_OFFSET = 3650


class SnoozeMutationAction(StrEnum):
    SNOOZE = "SNOOZE"
    UNSNOOZE = "UNSNOOZE"


@dataclass(frozen=True)
class SnoozeMutationRequest:
    action: SnoozeMutationAction
    message_key: str
    snooze_until_day_offset: int | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.action, SnoozeMutationAction):
            raise ValueError("action must be a closed SnoozeMutationAction")
        invalid_key = (
            not self.message_key
            or self.message_key != self.message_key.strip()
            or any(char.isspace() for char in self.message_key)
        )
        if invalid_key:
            raise ValueError("message_key must be a non-empty semantic token")

        if self.action is SnoozeMutationAction.SNOOZE:
            offset = self.snooze_until_day_offset
            if offset is None:
                raise ValueError("snooze requires snooze_until_day_offset")
            if isinstance(offset, bool) or not _MIN_DAY_OFFSET <= offset <= _MAX_DAY_OFFSET:
                raise ValueError("snooze_until_day_offset exceeds bounded window")
        elif self.snooze_until_day_offset is not None:
            raise ValueError("unsnooze must not carry snooze_until_day_offset")

    def to_payload(self) -> dict[str, object]:
        payload: dict[str, object] = {
            "action": self.action.value,
            "message_key": self.message_key,
        }
        if self.snooze_until_day_offset is not None:
            payload["snooze_until_day_offset"] = self.snooze_until_day_offset
        return payload


@dataclass(frozen=True)
class SnoozeMutationResult:
    action: SnoozeMutationAction
    message_key: str
    previous_state: SnoozeState
    read_back_state: SnoozeState
    read_back_until_day_offset: int | None
    changed: bool
    verified: bool
    synthetic: bool = True


def _current_marker(
    markers: tuple[PinSnoozeMarker, ...],
    message_key: str,
) -> PinSnoozeMarker | None:
    return next((item for item in markers if item.message_key == message_key), None)


def apply_fixture_snooze_mutation(
    fixture: OutlookMockFixture,
    request: SnoozeMutationRequest,
    *,
    readiness: OutlookReadinessReport,
    markers: tuple[PinSnoozeMarker, ...],
) -> tuple[tuple[PinSnoozeMarker, ...], SnoozeMutationResult]:
    """Apply one synthetic snooze transition and verify OUT-019 read-back."""
    if not fixture.synthetic:
        raise ValueError("OUT-036 fixture execution requires synthetic=true")
    if not readiness.ready_for_readonly_discovery:
        raise ValueError("Outlook read-only discovery is not ready")
    if not any(message.message_key == request.message_key for message in fixture.messages):
        raise ValueError("synthetic message_key not found")

    current = _current_marker(markers, request.message_key)
    previous = current.snooze_state if current is not None else SnoozeState.NOT_SNOOZED

    if request.action is SnoozeMutationAction.SNOOZE:
        if current is not None and current.is_pinned:
            raise ValueError("pinned message must be unpinned before snoozing")
        replacement = PinSnoozeMarker(
            message_key=request.message_key,
            snooze_state=SnoozeState.SNOOZED,
            snooze_until_day_offset=request.snooze_until_day_offset,
        )
        changed = current != replacement
        updated = tuple(
            item for item in markers if item.message_key != request.message_key
        ) + (replacement,)
    else:
        if current is None:
            updated = markers
            changed = False
        elif current.snooze_state is SnoozeState.NOT_SNOOZED:
            updated = markers
            changed = False
        else:
            updated = tuple(
                item for item in markers if item.message_key != request.message_key
            )
            changed = True

    read_back = read_fixture_pin_snooze_state(
        fixture,
        request.message_key,
        readiness=readiness,
        markers=updated,
    )
    expected_state = (
        SnoozeState.SNOOZED
        if request.action is SnoozeMutationAction.SNOOZE
        else SnoozeState.NOT_SNOOZED
    )
    expected_offset = (
        request.snooze_until_day_offset
        if request.action is SnoozeMutationAction.SNOOZE
        else None
    )
    verified = (
        read_back.snooze_state is expected_state
        and read_back.snooze_until_day_offset == expected_offset
    )
    if not verified:
        raise RuntimeError("synthetic snooze read-back did not prove requested state")

    return (
        updated,
        SnoozeMutationResult(
            action=request.action,
            message_key=request.message_key,
            previous_state=previous,
            read_back_state=read_back.snooze_state,
            read_back_until_day_offset=read_back.snooze_until_day_offset,
            changed=changed,
            verified=True,
        ),
    )


__all__ = [
    "SnoozeMutationAction",
    "SnoozeMutationRequest",
    "SnoozeMutationResult",
    "apply_fixture_snooze_mutation",
]
