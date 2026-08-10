"""Synthetic internal/external out-of-office message configuration for OUT-131."""

from __future__ import annotations

from dataclasses import dataclass

from m365_mcp.apps.outlook.readiness import OutlookReadinessReport


_MAX_MESSAGE_CHARS = 2000


@dataclass(frozen=True)
class OooMessageSettings:
    internal_message: str = ""
    external_message: str = ""
    external_enabled: bool = False
    synthetic: bool = True
    live_support_state: str = "UNOBSERVED"

    def __post_init__(self) -> None:
        for name in ("internal_message", "external_message"):
            value = getattr(self, name)
            if len(value) > _MAX_MESSAGE_CHARS:
                raise ValueError(f"{name} exceeds bounded size")
            if value and value != value.strip():
                raise ValueError(f"{name} must be trimmed")
        if self.external_enabled and not self.external_message:
            raise ValueError("external_enabled requires external_message")
        if not self.external_enabled and self.external_message:
            raise ValueError("external_message requires external_enabled")
        if not self.synthetic or self.live_support_state != "UNOBSERVED":
            raise ValueError("OOO messages must remain synthetic and live-unobserved")


@dataclass(frozen=True)
class OooMessageResult:
    changed: bool
    read_back: OooMessageSettings
    verified: bool = True
    dispatched: bool = False
    synthetic: bool = True


def configure_ooo_messages(
    current: OooMessageSettings,
    desired: OooMessageSettings,
    *,
    readiness: OutlookReadinessReport,
) -> tuple[OooMessageSettings, OooMessageResult]:
    """Configure synthetic OOO text only; never transmit an automatic reply."""
    if not readiness.ready_for_readonly_discovery:
        raise ValueError("Outlook read-only discovery is not ready")
    if not desired.synthetic or desired.live_support_state != "UNOBSERVED":
        raise ValueError("synthetic OOO message state is required")
    result = OooMessageResult(changed=desired != current, read_back=desired)
    if result.dispatched or not result.verified:
        raise RuntimeError("OOO message configuration failed closed")
    return desired, result


__all__ = [
    "OooMessageResult",
    "OooMessageSettings",
    "configure_ooo_messages",
]
