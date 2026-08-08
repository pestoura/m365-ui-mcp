"""Low-cardinality UI execution metrics for CORE-049.

The model records numeric execution characteristics and closed semantic stages.
It deliberately excludes selector strings, URLs, account/mailbox identity,
tenant content, browser profile paths, and other high-cardinality labels.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from m365_mcp.application_registry import ApplicationKey


class UIExecutionStage(StrEnum):
    """Closed, low-cardinality UI execution stages."""

    NAVIGATION = "NAVIGATION"
    READ = "READ"
    INTERACTION = "INTERACTION"
    READ_BACK = "READ_BACK"


class UIExecutionOutcome(StrEnum):
    """Closed result classes suitable for metrics labels."""

    SUCCESS = "SUCCESS"
    BLOCKED = "BLOCKED"
    CONTRACT_MISMATCH = "CONTRACT_MISMATCH"
    TIMEOUT = "TIMEOUT"
    FAILED = "FAILED"


@dataclass(frozen=True)
class UIExecutionSample:
    """One content-free execution sample."""

    application: ApplicationKey
    stage: UIExecutionStage
    outcome: UIExecutionOutcome
    duration_ms: int
    interaction_count: int = 0
    retry_count: int = 0
    read_back_count: int = 0

    def __post_init__(self) -> None:
        for field_name in (
            "duration_ms",
            "interaction_count",
            "retry_count",
            "read_back_count",
        ):
            if getattr(self, field_name) < 0:
                raise ValueError(f"{field_name} must be non-negative")

    def to_metrics(self) -> dict[str, str | int]:
        """Project only closed labels and numeric counters."""
        return {
            "application": self.application.value,
            "stage": self.stage.value,
            "outcome": self.outcome.value,
            "duration_ms": self.duration_ms,
            "interaction_count": self.interaction_count,
            "retry_count": self.retry_count,
            "read_back_count": self.read_back_count,
        }


@dataclass(frozen=True)
class UIExecutionAggregate:
    """Aggregate samples that share the same low-cardinality dimensions."""

    application: ApplicationKey
    stage: UIExecutionStage
    outcome: UIExecutionOutcome
    executions: int
    total_duration_ms: int
    total_interactions: int
    total_retries: int
    total_read_backs: int

    @property
    def average_duration_ms(self) -> float:
        if self.executions == 0:
            return 0.0
        return self.total_duration_ms / self.executions


def aggregate_ui_execution_samples(
    samples: tuple[UIExecutionSample, ...],
) -> tuple[UIExecutionAggregate, ...]:
    """Aggregate by application/stage/outcome only."""
    buckets: dict[
        tuple[ApplicationKey, UIExecutionStage, UIExecutionOutcome],
        list[UIExecutionSample],
    ] = {}
    for sample in samples:
        key = (sample.application, sample.stage, sample.outcome)
        buckets.setdefault(key, []).append(sample)

    aggregates: list[UIExecutionAggregate] = []
    for key in sorted(buckets, key=lambda item: tuple(part.value for part in item)):
        grouped = buckets[key]
        application, stage, outcome = key
        aggregates.append(
            UIExecutionAggregate(
                application=application,
                stage=stage,
                outcome=outcome,
                executions=len(grouped),
                total_duration_ms=sum(sample.duration_ms for sample in grouped),
                total_interactions=sum(sample.interaction_count for sample in grouped),
                total_retries=sum(sample.retry_count for sample in grouped),
                total_read_backs=sum(sample.read_back_count for sample in grouped),
            )
        )
    return tuple(aggregates)


__all__ = [
    "UIExecutionAggregate",
    "UIExecutionOutcome",
    "UIExecutionSample",
    "UIExecutionStage",
    "aggregate_ui_execution_samples",
]
