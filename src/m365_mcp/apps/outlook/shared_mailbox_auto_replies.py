"""Synthetic-only shared-mailbox automatic-reply settings for OUT-115.

This module models configuration state only. It never sends a reply and always
reports ``dispatched=False``; live delivery remains UNOBSERVED.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from m365_mcp.apps.outlook.shared_mailbox_context import SharedMailboxContext

_MAX_REPLY_CHARS = 2000


class AutoReplyAction(StrEnum):
    SET = "SET"
    DISABLE = "DISABLE"


@dataclass(frozen=True)
class SharedMailboxAutoReplySettings:
    enabled: bool
    internal_message: str = ""
    external_message: str = ""
    synthetic: bool = True

    def __post_init__(self) -> None:
        for name in ("internal_message", "external_message"):
            value = getattr(self, name)
            if len(value) > _MAX_REPLY_CHARS:
                raise ValueError(f"{name} exceeds bounded size")
            if value and value != value.strip():
                raise ValueError(f"{name} must be trimmed")
        if self.enabled and not (self.internal_message or self.external_message):
            raise ValueError("enabled automatic replies require message content")
        if not self.enabled and (self.internal_message or self.external_message):
            raise ValueError("disabled automatic replies cannot retain message content")


@dataclass(frozen=True)
class AutoReplyRequest:
    action: AutoReplyAction
    internal_message: str = ""
    external_message: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.action, AutoReplyAction):
            raise ValueError("action must be a closed AutoReplyAction")
        if self.action is AutoReplyAction.SET:
            SharedMailboxAutoReplySettings(
                enabled=True,
                internal_message=self.internal_message,
                external_message=self.external_message,
            )
        elif self.internal_message or self.external_message:
            raise ValueError("DISABLE does not accept message content")


@dataclass(frozen=True)
class AutoReplyResult:
    action: AutoReplyAction
    changed: bool
    read_back: SharedMailboxAutoReplySettings
    verified: bool
    dispatched: bool = False
    synthetic: bool = True


def mutate_shared_mailbox_auto_replies(
    context: SharedMailboxContext,
    current: SharedMailboxAutoReplySettings,
    request: AutoReplyRequest,
) -> tuple[SharedMailboxAutoReplySettings, AutoReplyResult]:
    """Change local synthetic settings only after shared-scope verification."""
    if not context.valid:
        raise ValueError("verified shared mailbox context is required")
    if request.action is AutoReplyAction.SET:
        desired = SharedMailboxAutoReplySettings(
            enabled=True,
            internal_message=request.internal_message,
            external_message=request.external_message,
        )
    else:
        desired = SharedMailboxAutoReplySettings(enabled=False)
    if desired.synthetic is not True:
        raise RuntimeError("automatic-reply state must remain synthetic")
    return desired, AutoReplyResult(
        action=request.action,
        changed=desired != current,
        read_back=desired,
        verified=True,
        dispatched=False,
    )


__all__ = [
    "AutoReplyAction",
    "AutoReplyRequest",
    "AutoReplyResult",
    "SharedMailboxAutoReplySettings",
    "mutate_shared_mailbox_auto_replies",
]
