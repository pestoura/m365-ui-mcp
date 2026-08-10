"""Synthetic sensitivity and message-security status reads for OUT-124."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from m365_mcp.apps.outlook.mock_ui import OutlookMockFixture
from m365_mcp.apps.outlook.readiness import OutlookReadinessReport


class SensitivityStatus(StrEnum):
    NORMAL = "NORMAL"
    CONFIDENTIAL = "CONFIDENTIAL"


class MessageProtectionStatus(StrEnum):
    NONE = "NONE"
    PROTECTED_SYNTHETIC = "PROTECTED_SYNTHETIC"


@dataclass(frozen=True)
class SyntheticMessageSecurityStatus:
    message_key: str
    sensitivity: SensitivityStatus
    protection: MessageProtectionStatus
    source: str = "SYNTHETIC_FIXTURE"
    live_support_state: str = "UNOBSERVED"
    synthetic: bool = True

    def to_projection(self) -> dict[str, object]:
        return {
            "message_key": self.message_key,
            "sensitivity": self.sensitivity.value,
            "protection": self.protection.value,
            "source": self.source,
            "live_support_state": self.live_support_state,
            "synthetic": self.synthetic,
        }


def read_message_security_status(
    fixture: OutlookMockFixture,
    message_key: str,
    *,
    readiness: OutlookReadinessReport,
) -> SyntheticMessageSecurityStatus:
    """Return tenant-neutral synthetic security metadata for one fixture message."""
    if not fixture.synthetic:
        raise ValueError("OUT-124 fixture execution requires synthetic=true")
    if not readiness.ready_for_readonly_discovery:
        raise ValueError("Outlook read-only discovery is not ready")
    if (
        not message_key
        or message_key != message_key.strip()
        or any(char.isspace() for char in message_key)
    ):
        raise ValueError("message_key must be a non-empty semantic token")
    if "@" in message_key or "://" in message_key:
        raise ValueError("message_key must not encode an address or URL")
    if not any(item.message_key == message_key for item in fixture.messages):
        raise ValueError("synthetic message_key not found")

    if message_key == "msg-002":
        return SyntheticMessageSecurityStatus(
            message_key=message_key,
            sensitivity=SensitivityStatus.CONFIDENTIAL,
            protection=MessageProtectionStatus.PROTECTED_SYNTHETIC,
        )
    return SyntheticMessageSecurityStatus(
        message_key=message_key,
        sensitivity=SensitivityStatus.NORMAL,
        protection=MessageProtectionStatus.NONE,
    )


__all__ = [
    "MessageProtectionStatus",
    "SensitivityStatus",
    "SyntheticMessageSecurityStatus",
    "read_message_security_status",
]
