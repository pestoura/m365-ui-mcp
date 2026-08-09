"""Fail-closed synthetic outbound intent foundation for Outlook Waves E/F.

No type in this module sends, schedules, replies to, forwards, resends, or otherwise
mutates a real Microsoft mailbox. Approval binding remains deliberately unavailable
until semantic Outlook outbound tools are registered and can participate in the
canonical CORE-035/CORE-036 approval-plan lifecycle.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class OutboundIntentKind(StrEnum):
    SCHEDULE_SEND = "SCHEDULE_SEND"
    SEND_DRAFT = "SEND_DRAFT"
    REPLY = "REPLY"
    REPLY_ALL = "REPLY_ALL"
    FORWARD = "FORWARD"
    RESEND = "RESEND"


class OutboundApprovalState(StrEnum):
    REQUIRED_NOT_BOUND = "REQUIRED_NOT_BOUND"


@dataclass(frozen=True)
class SyntheticOutboundIntent:
    """Tenant-neutral prepared outbound intent that cannot execute by itself."""

    intent_key: str
    kind: OutboundIntentKind
    draft_key: str
    source_message_key: str | None = None
    scheduled_slot: str | None = None
    approval_state: OutboundApprovalState = OutboundApprovalState.REQUIRED_NOT_BOUND
    synthetic: bool = True

    def __post_init__(self) -> None:
        for name in ("intent_key", "draft_key", "source_message_key", "scheduled_slot"):
            value = getattr(self, name)
            if value is None:
                continue
            if not value or value != value.strip() or any(char.isspace() for char in value):
                raise ValueError(f"{name} must be a non-empty semantic token")
        if not self.synthetic:
            raise ValueError("outbound foundation is synthetic-only")
        if self.approval_state is not OutboundApprovalState.REQUIRED_NOT_BOUND:
            raise ValueError("outbound approval cannot be pre-bound before tool registration")
        if self.kind is OutboundIntentKind.SCHEDULE_SEND:
            if self.scheduled_slot is None or self.source_message_key is not None:
                raise ValueError("schedule-send requires slot and no source_message_key")
        elif self.kind is OutboundIntentKind.SEND_DRAFT:
            if self.scheduled_slot is not None or self.source_message_key is not None:
                raise ValueError("send-draft accepts only draft_key")
        elif self.source_message_key is None or self.scheduled_slot is not None:
            raise ValueError(
                "message-derived outbound intents require source_message_key and no schedule"
            )

    @property
    def executable(self) -> bool:
        """Outbound execution stays fail-closed until canonical approval is bound."""
        return False

    def to_projection(self) -> dict[str, object]:
        return {
            "intent_key": self.intent_key,
            "kind": self.kind.value,
            "draft_key": self.draft_key,
            "source_message_key": self.source_message_key,
            "scheduled_slot": self.scheduled_slot,
            "approval_state": self.approval_state.value,
            "approval_required": True,
            "executable": False,
            "synthetic": True,
        }


def require_outbound_execution_blocked(intent: SyntheticOutboundIntent) -> None:
    """Explicit guard proving prepared synthetic intents cannot execute."""
    if not intent.synthetic or intent.executable:
        raise RuntimeError("outbound intent unexpectedly became executable")
    message = (
        "outbound execution blocked: semantic tool registration and "
        "canonical HITL approval required"
    )
    raise PermissionError(message)


__all__ = [
    "OutboundApprovalState",
    "OutboundIntentKind",
    "SyntheticOutboundIntent",
    "require_outbound_execution_blocked",
]
