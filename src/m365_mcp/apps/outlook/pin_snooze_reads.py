"""Synthetic-only Outlook pin/snooze read state for OUT-019.

Pin and snooze are distinct list-presentation states and are modelled together
because both determine whether a message is surfaced or deferred in a mailbox
listing. Snooze uses bounded relative day offsets, consistent with OUT-018.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from m365_mcp.apps.outlook.mock_ui import OutlookMockFixture
from m365_mcp.apps.outlook.readiness import OutlookReadinessReport

_MIN_DAY_OFFSET = -3650
_MAX_DAY_OFFSET = 3650


class SnoozeState(StrEnum):
    """Closed snooze states for read-only listing semantics."""

    NOT_SNOOZED = "NOT_SNOOZED"
    SNOOZED = "SNOOZED"


@dataclass(frozen=True)
class PinSnoozeMarker:
    """Tenant-neutral pin/snooze marker bound to one synthetic message."""

    message_key: str
    is_pinned: bool = False
    snooze_state: SnoozeState = SnoozeState.NOT_SNOOZED
    snooze_until_day_offset: int | None = None

    def __post_init__(self) -> None:
        invalid_key = (
            not self.message_key
            or self.message_key != self.message_key.strip()
            or any(char.isspace() for char in self.message_key)
        )
        if invalid_key:
            raise ValueError("message_key must be a non-empty semantic token")
        if not isinstance(self.is_pinned, bool):
            raise ValueError("is_pinned must be a boolean")
        if not isinstance(self.snooze_state, SnoozeState):
            raise ValueError("snooze_state must be a closed SnoozeState")

        offset = self.snooze_until_day_offset
        if self.snooze_state is SnoozeState.SNOOZED:
            if offset is None:
                raise ValueError("a snoozed message requires snooze_until_day_offset")
        elif offset is not None:
            raise ValueError("snooze_until_day_offset is only valid for a snoozed message")

        if offset is not None:
            if not isinstance(offset, int) or isinstance(offset, bool):
                raise ValueError("snooze_until_day_offset must be an integer day offset")
            if not _MIN_DAY_OFFSET <= offset <= _MAX_DAY_OFFSET:
                raise ValueError("snooze_until_day_offset exceeds the bounded day-offset window")

        if self.is_pinned and self.snooze_state is SnoozeState.SNOOZED:
            raise ValueError("a message must not be pinned and snoozed simultaneously")


@dataclass(frozen=True)
class PinSnoozeReadState:
    """Read-only pin/snooze projection for one synthetic message."""

    message_key: str
    is_pinned: bool
    snooze_state: SnoozeState
    snooze_until_day_offset: int | None
    is_snooze_elapsed: bool
    is_hidden_from_default_list: bool
    synthetic: bool

    def to_projection(self) -> dict[str, object]:
        return {
            "message_key": self.message_key,
            "is_pinned": self.is_pinned,
            "snooze_state": self.snooze_state.value,
            "snooze_until_day_offset": self.snooze_until_day_offset,
            "is_snooze_elapsed": self.is_snooze_elapsed,
            "is_hidden_from_default_list": self.is_hidden_from_default_list,
            "synthetic": self.synthetic,
        }


@dataclass(frozen=True)
class PinSnoozeListResult:
    """Deterministic bounded pin/snooze listing across the synthetic fixture."""

    items: tuple[PinSnoozeReadState, ...]
    pinned_count: int
    snoozed_count: int
    hidden_count: int
    reference_day_offset: int
    synthetic: bool


def default_synthetic_pin_snooze_markers() -> tuple[PinSnoozeMarker, ...]:
    """Return the explicit synthetic pin/snooze catalog."""
    return (
        PinSnoozeMarker(message_key="msg-001", is_pinned=True),
        PinSnoozeMarker(
            message_key="msg-002",
            snooze_state=SnoozeState.SNOOZED,
            snooze_until_day_offset=3,
        ),
    )


def _validate(
    fixture: OutlookMockFixture,
    markers: tuple[PinSnoozeMarker, ...],
) -> None:
    keys = tuple(marker.message_key for marker in markers)
    if len(set(keys)) != len(keys):
        raise ValueError("pin/snooze markers must be unique per message_key")
    known = {message.message_key for message in fixture.messages}
    for marker in markers:
        if marker.message_key not in known:
            raise ValueError("pin/snooze marker references unknown synthetic message_key")


def _project(marker: PinSnoozeMarker, reference_day_offset: int) -> PinSnoozeReadState:
    offset = marker.snooze_until_day_offset
    snoozed = marker.snooze_state is SnoozeState.SNOOZED
    elapsed = snoozed and offset is not None and offset <= reference_day_offset
    return PinSnoozeReadState(
        message_key=marker.message_key,
        is_pinned=marker.is_pinned,
        snooze_state=marker.snooze_state,
        snooze_until_day_offset=offset,
        is_snooze_elapsed=elapsed,
        is_hidden_from_default_list=snoozed and not elapsed,
        synthetic=True,
    )


def read_fixture_pin_snooze_state(
    fixture: OutlookMockFixture,
    message_key: str,
    *,
    readiness: OutlookReadinessReport,
    markers: tuple[PinSnoozeMarker, ...] | None = None,
    reference_day_offset: int = 0,
) -> PinSnoozeReadState:
    """Read pin/snooze state for one synthetic message, defaulting to neither."""
    if not message_key or message_key != message_key.strip():
        raise ValueError("message_key must be a non-empty semantic token")
    if not fixture.synthetic:
        raise ValueError("OUT-019 fixture execution requires synthetic=true")
    if not readiness.ready_for_readonly_discovery:
        raise ValueError("Outlook read-only discovery is not ready")
    if not _MIN_DAY_OFFSET <= reference_day_offset <= _MAX_DAY_OFFSET:
        raise ValueError("reference_day_offset exceeds the bounded day-offset window")
    if not any(message.message_key == message_key for message in fixture.messages):
        raise ValueError("synthetic message_key not found")

    catalog = default_synthetic_pin_snooze_markers() if markers is None else markers
    _validate(fixture, catalog)

    match = next((marker for marker in catalog if marker.message_key == message_key), None)
    if match is None:
        match = PinSnoozeMarker(message_key=message_key)
    return _project(match, reference_day_offset)


def list_fixture_pin_snooze_state(
    fixture: OutlookMockFixture,
    *,
    readiness: OutlookReadinessReport,
    markers: tuple[PinSnoozeMarker, ...] | None = None,
    reference_day_offset: int = 0,
) -> PinSnoozeListResult:
    """List pin/snooze state for every synthetic message with bounded counters."""
    if not fixture.synthetic:
        raise ValueError("OUT-019 fixture execution requires synthetic=true")
    if not readiness.ready_for_readonly_discovery:
        raise ValueError("Outlook read-only discovery is not ready")
    if not _MIN_DAY_OFFSET <= reference_day_offset <= _MAX_DAY_OFFSET:
        raise ValueError("reference_day_offset exceeds the bounded day-offset window")

    catalog = default_synthetic_pin_snooze_markers() if markers is None else markers
    _validate(fixture, catalog)

    by_key = {marker.message_key: marker for marker in catalog}
    items = tuple(
        _project(
            by_key.get(message.message_key, PinSnoozeMarker(message_key=message.message_key)),
            reference_day_offset,
        )
        for message in fixture.messages
    )
    return PinSnoozeListResult(
        items=items,
        pinned_count=sum(1 for item in items if item.is_pinned),
        snoozed_count=sum(1 for item in items if item.snooze_state is SnoozeState.SNOOZED),
        hidden_count=sum(1 for item in items if item.is_hidden_from_default_list),
        reference_day_offset=reference_day_offset,
        synthetic=True,
    )


__all__ = [
    "PinSnoozeListResult",
    "PinSnoozeMarker",
    "PinSnoozeReadState",
    "SnoozeState",
    "default_synthetic_pin_snooze_markers",
    "list_fixture_pin_snooze_state",
    "read_fixture_pin_snooze_state",
]
