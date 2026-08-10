"""Synthetic governed phishing-report intent preparation for OUT-121."""

from __future__ import annotations

from dataclasses import dataclass

from m365_mcp.apps.outlook.mock_ui import OutlookMockFixture
from m365_mcp.apps.outlook.outbound_models import OutboundApprovalState
from m365_mcp.apps.outlook.readiness import OutlookReadinessReport


@dataclass(frozen=True)
class PhishingReportRequest:
    message_key: str

    def __post_init__(self) -> None:
        if (
            not self.message_key
            or self.message_key != self.message_key.strip()
            or any(char.isspace() for char in self.message_key)
        ):
            raise ValueError("message_key must be a non-empty semantic token")
        if "@" in self.message_key or "://" in self.message_key:
            raise ValueError("message_key must not encode an address or URL")


@dataclass(frozen=True)
class PhishingReportIntent:
    report_key: str
    message_key: str
    approval_state: OutboundApprovalState = OutboundApprovalState.REQUIRED_NOT_BOUND
    dispatched: bool = False
    synthetic: bool = True

    @property
    def executable(self) -> bool:
        return False

    def to_projection(self) -> dict[str, object]:
        return {
            "report_key": self.report_key,
            "message_key": self.message_key,
            "report_type": "PHISHING",
            "approval_state": self.approval_state.value,
            "approval_required": True,
            "executable": False,
            "dispatched": False,
            "synthetic": True,
        }


def prepare_phishing_report(
    fixture: OutlookMockFixture,
    request: PhishingReportRequest,
    *,
    readiness: OutlookReadinessReport,
) -> PhishingReportIntent:
    """Prepare a phishing report over an opaque synthetic message key."""
    if not fixture.synthetic:
        raise ValueError("OUT-121 fixture execution requires synthetic=true")
    if not readiness.ready_for_readonly_discovery:
        raise ValueError("Outlook read-only discovery is not ready")
    if not any(item.message_key == request.message_key for item in fixture.messages):
        raise ValueError("synthetic message_key not found")

    intent = PhishingReportIntent(
        report_key=f"report-phishing-{request.message_key}",
        message_key=request.message_key,
    )
    if intent.executable or intent.dispatched:
        raise RuntimeError("synthetic phishing-report intent unexpectedly became executable")
    return intent


__all__ = [
    "PhishingReportIntent",
    "PhishingReportRequest",
    "prepare_phishing_report",
]
