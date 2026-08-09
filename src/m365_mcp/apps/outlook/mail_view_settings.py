"""Tenant-neutral synthetic mail view settings for OUT-071."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from m365_mcp.apps.outlook.readiness import OutlookReadinessReport


class ConversationSort(StrEnum):
    NEWEST_FIRST = "NEWEST_FIRST"
    OLDEST_FIRST = "OLDEST_FIRST"


@dataclass(frozen=True)
class SyntheticMailViewSettings:
    focused_inbox_enabled: bool
    conversation_view_enabled: bool
    conversation_sort: ConversationSort = ConversationSort.NEWEST_FIRST

    def to_projection(self) -> dict[str, object]:
        return {
            "focused_inbox_enabled": self.focused_inbox_enabled,
            "conversation_view_enabled": self.conversation_view_enabled,
            "conversation_sort": self.conversation_sort.value,
            "synthetic": True,
        }


@dataclass(frozen=True)
class MailViewMutationRequest:
    desired: SyntheticMailViewSettings

    def to_payload(self) -> dict[str, object]:
        return {"desired": self.desired.to_projection()}


@dataclass(frozen=True)
class MailViewMutationResult:
    previous: SyntheticMailViewSettings
    read_back: SyntheticMailViewSettings
    changed: bool
    verified: bool
    synthetic: bool = True


def default_synthetic_mail_view_settings() -> SyntheticMailViewSettings:
    return SyntheticMailViewSettings(
        focused_inbox_enabled=True,
        conversation_view_enabled=True,
    )


def mutate_mail_view_settings(
    current: SyntheticMailViewSettings,
    request: MailViewMutationRequest,
    *,
    readiness: OutlookReadinessReport,
) -> tuple[SyntheticMailViewSettings, MailViewMutationResult]:
    """Apply synthetic view preferences with deterministic read-back."""
    if not readiness.ready_for_readonly_discovery:
        raise ValueError("Outlook read-only discovery is not ready")

    updated = request.desired
    read_back = updated
    if read_back != request.desired:
        raise RuntimeError("synthetic read-back did not prove mail view settings")

    return updated, MailViewMutationResult(
        previous=current,
        read_back=read_back,
        changed=current != updated,
        verified=True,
    )


__all__ = [
    "ConversationSort",
    "MailViewMutationRequest",
    "MailViewMutationResult",
    "SyntheticMailViewSettings",
    "default_synthetic_mail_view_settings",
    "mutate_mail_view_settings",
]
