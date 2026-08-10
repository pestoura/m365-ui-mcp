"""Synthetic primary-mailbox automatic-reply mode configuration for OUT-130."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from m365_mcp.apps.outlook.readiness import OutlookReadinessReport


class AutomaticReplyMode(StrEnum):
    DISABLED = "DISABLED"
    ENABLED = "ENABLED"


@dataclass(frozen=True)
class AutomaticReplySettings:
    mode: AutomaticReplyMode = AutomaticReplyMode.DISABLED
    synthetic: bool = True
    live_support_state: str = "UNOBSERVED"

    def __post_init__(self) -> None:
        if not isinstance(self.mode, AutomaticReplyMode):
            raise ValueError("mode must be a closed AutomaticReplyMode")
        if not self.synthetic or self.live_support_state != "UNOBSERVED":
            raise ValueError("automatic-reply state must remain synthetic and live-unobserved")


@dataclass(frozen=True)
class AutomaticReplyResult:
    changed: bool
    read_back: AutomaticReplySettings
    verified: bool = True
    dispatched: bool = False
    synthetic: bool = True


def read_automatic_reply_settings(
    current: AutomaticReplySettings,
    *,
    readiness: OutlookReadinessReport,
) -> AutomaticReplySettings:
    """Read local synthetic primary-mailbox automatic-reply mode."""
    if not readiness.ready_for_readonly_discovery:
        raise ValueError("Outlook read-only discovery is not ready")
    return current


def configure_automatic_reply_mode(
    current: AutomaticReplySettings,
    mode: AutomaticReplyMode,
    *,
    readiness: OutlookReadinessReport,
) -> tuple[AutomaticReplySettings, AutomaticReplyResult]:
    """Configure local synthetic reply mode without sending any reply."""
    if not readiness.ready_for_readonly_discovery:
        raise ValueError("Outlook read-only discovery is not ready")
    if not isinstance(mode, AutomaticReplyMode):
        raise ValueError("mode must be a closed AutomaticReplyMode")
    updated = AutomaticReplySettings(mode=mode)
    result = AutomaticReplyResult(changed=updated != current, read_back=updated)
    if result.dispatched or not result.verified:
        raise RuntimeError("automatic-reply configuration failed closed")
    return updated, result


__all__ = [
    "AutomaticReplyMode",
    "AutomaticReplyResult",
    "AutomaticReplySettings",
    "configure_automatic_reply_mode",
    "read_automatic_reply_settings",
]
