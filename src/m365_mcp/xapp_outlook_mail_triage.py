"""Synthetic-only Outlook mail triage recommendations for XAPP-021.

The composite classifies bounded message-list metadata only. It does not move,
mark, delete, reply to, or otherwise mutate any message.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from m365_mcp.apps.outlook.message_list import MessageListResult

_MAX_TRIAGE_ITEMS = 100


class OutlookTriageDisposition(StrEnum):
    REVIEW_ATTACHMENT = "REVIEW_ATTACHMENT"
    REVIEW_UNREAD = "REVIEW_UNREAD"
    NO_ACTION = "NO_ACTION"


@dataclass(frozen=True)
class OutlookTriageRecommendation:
    message_key: str
    disposition: OutlookTriageDisposition


@dataclass(frozen=True)
class OutlookMailTriagePlan:
    recommendations: tuple[OutlookTriageRecommendation, ...]
    synthetic: bool = True
    live_observed: bool = False
    execution_performed: bool = False

    def __post_init__(self) -> None:
        if not self.synthetic:
            raise ValueError("Outlook mail triage must remain synthetic")
        if self.live_observed:
            raise ValueError("Outlook mail triage must not claim live observation")
        if self.execution_performed:
            raise ValueError("Outlook mail triage must not execute mutations")
        keys = tuple(item.message_key for item in self.recommendations)
        if len(keys) != len(set(keys)):
            raise ValueError("Outlook mail triage message keys must be unique")


def _disposition(*, is_read: bool, has_attachments: bool) -> OutlookTriageDisposition:
    if not is_read and has_attachments:
        return OutlookTriageDisposition.REVIEW_ATTACHMENT
    if not is_read:
        return OutlookTriageDisposition.REVIEW_UNREAD
    return OutlookTriageDisposition.NO_ACTION


def plan_synthetic_mail_triage(
    result: MessageListResult,
    *,
    max_items: int = 50,
) -> OutlookMailTriagePlan:
    """Return deterministic recommendations from synthetic list metadata only."""
    if not result.synthetic:
        raise ValueError("XAPP-021 requires a synthetic Outlook message-list result")
    if not 1 <= max_items <= _MAX_TRIAGE_ITEMS:
        raise ValueError("max_items must be between 1 and 100")

    recommendations = tuple(
        OutlookTriageRecommendation(
            message_key=item.message_key,
            disposition=_disposition(
                is_read=item.is_read,
                has_attachments=item.has_attachments,
            ),
        )
        for item in sorted(result.items, key=lambda candidate: candidate.message_key)[
            :max_items
        ]
    )
    return OutlookMailTriagePlan(recommendations=recommendations)


__all__ = [
    "OutlookMailTriagePlan",
    "OutlookTriageDisposition",
    "OutlookTriageRecommendation",
    "plan_synthetic_mail_triage",
]
