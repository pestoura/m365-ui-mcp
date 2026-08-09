"""Tenant-neutral synthetic recall-status reporting for OUT-057."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class RecallStatus(StrEnum):
    PENDING = "PENDING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    PARTIAL = "PARTIAL"
    UNKNOWN = "UNKNOWN"


def _semantic_token(value: str, name: str) -> str:
    if not value or value != value.strip() or any(char.isspace() for char in value):
        raise ValueError(f"{name} must be a non-empty semantic token")
    return value


@dataclass(frozen=True)
class SyntheticRecallStatus:
    recall_key: str
    sent_message_key: str
    status: RecallStatus
    attempted_count: int
    succeeded_count: int
    failed_count: int
    synthetic: bool = True

    def __post_init__(self) -> None:
        _semantic_token(self.recall_key, "recall_key")
        _semantic_token(self.sent_message_key, "sent_message_key")
        if not self.synthetic:
            raise ValueError("recall status must be synthetic")
        counts = (self.attempted_count, self.succeeded_count, self.failed_count)
        if any(value < 0 for value in counts):
            raise ValueError("recall status counts must be non-negative")
        if self.succeeded_count + self.failed_count > self.attempted_count:
            raise ValueError("resolved recall counts cannot exceed attempted_count")
        if self.status is RecallStatus.SUCCEEDED:
            if self.attempted_count == 0 or self.succeeded_count != self.attempted_count:
                raise ValueError("SUCCEEDED requires all attempted recalls to succeed")
            if self.failed_count != 0:
                raise ValueError("SUCCEEDED cannot include failures")
        elif self.status is RecallStatus.FAILED:
            if self.attempted_count == 0 or self.failed_count != self.attempted_count:
                raise ValueError("FAILED requires all attempted recalls to fail")
            if self.succeeded_count != 0:
                raise ValueError("FAILED cannot include successes")
        elif self.status is RecallStatus.PARTIAL:
            if self.succeeded_count == 0 or self.failed_count == 0:
                raise ValueError("PARTIAL requires both success and failure evidence")

    def to_projection(self) -> dict[str, object]:
        return {
            "recall_key": self.recall_key,
            "sent_message_key": self.sent_message_key,
            "status": self.status.value,
            "attempted_count": self.attempted_count,
            "succeeded_count": self.succeeded_count,
            "failed_count": self.failed_count,
            "synthetic": True,
        }


def read_recall_status(
    statuses: tuple[SyntheticRecallStatus, ...],
    recall_key: str,
) -> SyntheticRecallStatus:
    """Return exactly one known synthetic status; ambiguous/missing keys fail closed."""
    _semantic_token(recall_key, "recall_key")
    matches = tuple(item for item in statuses if item.recall_key == recall_key)
    if len(matches) != 1:
        raise ValueError("recall_key must resolve to exactly one synthetic status")
    return matches[0]


__all__ = ["RecallStatus", "SyntheticRecallStatus", "read_recall_status"]
