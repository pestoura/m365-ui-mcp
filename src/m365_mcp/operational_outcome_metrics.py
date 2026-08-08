"""Low-cardinality operational outcome metrics for CORE-050."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from m365_mcp.application_registry import ApplicationKey


class OperationalSignal(StrEnum):
    DRIFT = "DRIFT"
    READ_BACK = "READ_BACK"
    INDETERMINATE = "INDETERMINATE"


class OperationalOutcome(StrEnum):
    CLEAN = "CLEAN"
    DETECTED = "DETECTED"
    EFFECT_PRESENT = "EFFECT_PRESENT"
    EFFECT_ABSENT = "EFFECT_ABSENT"
    AMBIGUOUS = "AMBIGUOUS"
    RESOLVED = "RESOLVED"


@dataclass(frozen=True)
class OperationalOutcomeSample:
    application: ApplicationKey
    signal: OperationalSignal
    outcome: OperationalOutcome
    occurrences: int = 1

    def __post_init__(self) -> None:
        if self.occurrences <= 0:
            raise ValueError("occurrences must be positive")
        allowed = {
            OperationalSignal.DRIFT: {
                OperationalOutcome.CLEAN,
                OperationalOutcome.DETECTED,
                OperationalOutcome.RESOLVED,
            },
            OperationalSignal.READ_BACK: {
                OperationalOutcome.EFFECT_PRESENT,
                OperationalOutcome.EFFECT_ABSENT,
                OperationalOutcome.AMBIGUOUS,
            },
            OperationalSignal.INDETERMINATE: {
                OperationalOutcome.DETECTED,
                OperationalOutcome.RESOLVED,
            },
        }
        if self.outcome not in allowed[self.signal]:
            raise ValueError("outcome is invalid for operational signal")

    def to_metrics(self) -> dict[str, str | int]:
        return {
            "application": self.application.value,
            "signal": self.signal.value,
            "outcome": self.outcome.value,
            "occurrences": self.occurrences,
        }


def aggregate_operational_outcomes(
    samples: tuple[OperationalOutcomeSample, ...],
) -> tuple[OperationalOutcomeSample, ...]:
    totals: dict[tuple[ApplicationKey, OperationalSignal, OperationalOutcome], int] = {}
    for sample in samples:
        key = (sample.application, sample.signal, sample.outcome)
        totals[key] = totals.get(key, 0) + sample.occurrences
    return tuple(
        OperationalOutcomeSample(application, signal, outcome, occurrences)
        for (application, signal, outcome), occurrences in sorted(
            totals.items(),
            key=lambda item: tuple(part.value for part in item[0]),
        )
    )


__all__ = [
    "OperationalOutcome",
    "OperationalOutcomeSample",
    "OperationalSignal",
    "aggregate_operational_outcomes",
]
