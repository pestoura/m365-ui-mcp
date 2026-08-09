"""Synthetic sent-item read-back and outbound retry strategy for OUT-055.

The module never sends mail. It only classifies tenant-neutral synthetic evidence
and feeds that evidence into CORE-038 replay protection so an uncertain outbound
operation cannot be blindly repeated.
"""

from __future__ import annotations

from dataclasses import dataclass

from m365_mcp.apps.outlook.outbound_models import SyntheticOutboundIntent
from m365_mcp.idempotency_v2 import (
    IdempotencyRecordV2,
    ReadBackOutcome,
    RetryAction,
    reserve_operation,
    resolve_retry,
)
from m365_mcp.state_identity import StateIdentity

_OUTBOUND_OPERATION = "outlook_outbound_commit"


def _semantic_token(value: str, name: str) -> str:
    if not value or value != value.strip() or any(char.isspace() for char in value):
        raise ValueError(f"{name} must be a non-empty semantic token")
    return value


@dataclass(frozen=True)
class SyntheticSentItemObservation:
    """Tenant-neutral correlation evidence for one synthetic sent item."""

    intent_key: str
    sent_message_key: str
    synthetic: bool = True

    def __post_init__(self) -> None:
        _semantic_token(self.intent_key, "intent_key")
        _semantic_token(self.sent_message_key, "sent_message_key")
        if not self.synthetic:
            raise ValueError("sent-item observation must be synthetic")


@dataclass(frozen=True)
class SentItemReadBackResult:
    """Bounded CORE-038 evidence derived from synthetic sent-item observations."""

    outcome: ReadBackOutcome
    candidate_count: int
    matched_message_key: str | None = None
    synthetic: bool = True

    def __post_init__(self) -> None:
        if self.candidate_count < 0:
            raise ValueError("candidate_count must be non-negative")
        if not self.synthetic:
            raise ValueError("sent-item read-back must be synthetic")
        if self.outcome is ReadBackOutcome.EFFECT_PRESENT:
            if self.candidate_count != 1 or self.matched_message_key is None:
                raise ValueError("EFFECT_PRESENT requires exactly one matched message")
            _semantic_token(self.matched_message_key, "matched_message_key")
        elif self.matched_message_key is not None:
            raise ValueError("only EFFECT_PRESENT may expose matched_message_key")


def evaluate_sent_item_read_back(
    intent: SyntheticOutboundIntent,
    observations: tuple[SyntheticSentItemObservation, ...],
) -> SentItemReadBackResult:
    """Classify exact intent correlation as absent, present or ambiguous."""
    if not intent.synthetic:
        raise ValueError("OUT-055 accepts synthetic outbound intents only")
    if any(not item.synthetic for item in observations):
        raise ValueError("OUT-055 accepts synthetic observations only")

    matches = tuple(item for item in observations if item.intent_key == intent.intent_key)
    if not matches:
        return SentItemReadBackResult(
            outcome=ReadBackOutcome.EFFECT_ABSENT,
            candidate_count=0,
        )
    if len(matches) == 1:
        return SentItemReadBackResult(
            outcome=ReadBackOutcome.EFFECT_PRESENT,
            candidate_count=1,
            matched_message_key=matches[0].sent_message_key,
        )
    return SentItemReadBackResult(
        outcome=ReadBackOutcome.AMBIGUOUS,
        candidate_count=len(matches),
    )


def reserve_outbound_intent(
    identity: StateIdentity,
    intent: SyntheticOutboundIntent,
) -> IdempotencyRecordV2:
    """Reserve a synthetic outbound effect with mandatory post-effect read-back."""
    if not intent.synthetic or intent.executable:
        raise ValueError("only non-executable synthetic outbound intents may be reserved")
    return reserve_operation(
        _OUTBOUND_OPERATION,
        identity,
        intent.to_projection(),
        read_back_required=True,
    )


def resolve_outbound_retry(
    record: IdempotencyRecordV2,
    identity: StateIdentity,
    intent: SyntheticOutboundIntent,
    read_back: SentItemReadBackResult,
) -> RetryAction:
    """Resolve retry through CORE-038 using the exact sent-item read-back outcome."""
    return resolve_retry(
        record,
        operation=_OUTBOUND_OPERATION,
        identity=identity,
        payload=intent.to_projection(),
        read_back=read_back.outcome,
    )


__all__ = [
    "SentItemReadBackResult",
    "SyntheticSentItemObservation",
    "evaluate_sent_item_read_back",
    "reserve_outbound_intent",
    "resolve_outbound_retry",
]
