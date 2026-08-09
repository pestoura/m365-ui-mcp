"""Bounded tenant-neutral synthetic recurrence/series handling for OUT-084."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from m365_mcp.apps.outlook.readiness import OutlookReadinessReport

_MAX_OCCURRENCES = 100
_MAX_INTERVAL = 12


class RecurrenceFrequency(StrEnum):
    DAILY = "DAILY"
    WEEKLY = "WEEKLY"
    MONTHLY = "MONTHLY"


class RecurrenceMutationAction(StrEnum):
    UPSERT = "UPSERT"
    DELETE = "DELETE"


@dataclass(frozen=True)
class SyntheticRecurrenceSeries:
    series_key: str
    anchor_event_key: str
    frequency: RecurrenceFrequency
    interval: int
    occurrence_count: int

    def __post_init__(self) -> None:
        _validate_key("series_key", self.series_key)
        _validate_key("anchor_event_key", self.anchor_event_key)
        if not isinstance(self.interval, int) or isinstance(self.interval, bool):
            raise ValueError("interval must be an integer")
        if not 1 <= self.interval <= _MAX_INTERVAL:
            raise ValueError("interval exceeds the bounded synthetic range")
        if not isinstance(self.occurrence_count, int) or isinstance(
            self.occurrence_count, bool
        ):
            raise ValueError("occurrence_count must be an integer")
        if not 1 <= self.occurrence_count <= _MAX_OCCURRENCES:
            raise ValueError("occurrence_count exceeds the bounded synthetic range")

    def occurrence_key(self, ordinal: int) -> str:
        if not isinstance(ordinal, int) or isinstance(ordinal, bool):
            raise ValueError("ordinal must be an integer")
        if not 1 <= ordinal <= self.occurrence_count:
            raise ValueError("ordinal is outside the synthetic series")
        return f"{self.series_key}-occ-{ordinal:03d}"

    def to_payload(self) -> dict[str, object]:
        return {
            "series_key": self.series_key,
            "anchor_event_key": self.anchor_event_key,
            "frequency": self.frequency.value,
            "interval": self.interval,
            "occurrence_count": self.occurrence_count,
        }


@dataclass(frozen=True)
class RecurrenceMutationRequest:
    action: RecurrenceMutationAction
    series: SyntheticRecurrenceSeries | None = None
    series_key: str | None = None

    def __post_init__(self) -> None:
        if self.action is RecurrenceMutationAction.UPSERT:
            if self.series is None or self.series_key is not None:
                raise ValueError("upsert requires series and no series_key")
        else:
            if self.series is not None or self.series_key is None:
                raise ValueError("delete requires series_key and no series")
            _validate_key("series_key", self.series_key)


@dataclass(frozen=True)
class RecurrenceMutationResult:
    series_key: str
    changed: bool
    verified: bool
    occurrence_keys: tuple[str, ...]
    synthetic: bool = True


def _validate_key(name: str, value: str) -> None:
    if not value or value != value.strip() or any(char.isspace() for char in value):
        raise ValueError(f"{name} must be a non-empty semantic token")


def mutate_recurrence_series(
    series: tuple[SyntheticRecurrenceSeries, ...],
    request: RecurrenceMutationRequest,
    *,
    readiness: OutlookReadinessReport,
) -> tuple[tuple[SyntheticRecurrenceSeries, ...], RecurrenceMutationResult]:
    """Upsert/delete one synthetic series and expose bounded occurrence identities."""
    if not readiness.ready_for_readonly_discovery:
        raise ValueError("Outlook read-only discovery is not ready")
    keys = tuple(item.series_key for item in series)
    if len(keys) != len(set(keys)):
        raise ValueError("recurrence catalog contains duplicate series_key values")

    if request.action is RecurrenceMutationAction.UPSERT:
        assert request.series is not None
        series_key = request.series.series_key
        current = next((item for item in series if item.series_key == series_key), None)
        if current is None:
            updated = (*series, request.series)
            changed = True
        else:
            updated = tuple(
                request.series if item.series_key == series_key else item for item in series
            )
            changed = current != request.series
        read_back = next(item for item in updated if item.series_key == series_key)
        if read_back != request.series:
            raise RuntimeError("synthetic read-back did not prove recurrence series")
        occurrence_keys = tuple(
            read_back.occurrence_key(ordinal)
            for ordinal in range(1, read_back.occurrence_count + 1)
        )
    else:
        assert request.series_key is not None
        series_key = request.series_key
        updated = tuple(item for item in series if item.series_key != series_key)
        changed = len(updated) != len(series)
        if any(item.series_key == series_key for item in updated):
            raise RuntimeError("synthetic read-back did not prove series deletion")
        occurrence_keys = ()

    return updated, RecurrenceMutationResult(
        series_key=series_key,
        changed=changed,
        verified=True,
        occurrence_keys=occurrence_keys,
    )


__all__ = [
    "RecurrenceFrequency",
    "RecurrenceMutationAction",
    "RecurrenceMutationRequest",
    "RecurrenceMutationResult",
    "SyntheticRecurrenceSeries",
    "mutate_recurrence_series",
]
