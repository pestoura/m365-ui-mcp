"""Synthetic governed Junk/not-junk report intent preparation for OUT-120."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from m365_mcp.apps.outlook.mock_ui import OutlookMockFixture
from m365_mcp.apps.outlook.outbound_models import OutboundApprovalState
from m365_mcp.apps.outlook.readiness import OutlookReadinessReport


class JunkReportAction(StrEnum):
    JUNK = "JUNK"
    NOT_JUNK = "NOT_JUNK"


@dataclass(frozen=True)
class JunkReportRequest:
    message_key: str
    action: JunkReportAction

    def __post_init__(self) -> None:
        if (
            not self.message_key
            or self.message_key != self.message_key.strip()
            or any(char.isspace() for char in self.message_key)
        ):
            raise ValueError("message_key must be a non-empty semantic token")
        if "@" in self.message_key:
            raise ValueError("message_key must not encode an address identity")
        if not isinstance(self.action, JunkReportAction):
            raise ValueError("action must be a closed JunkReportAction")


@dataclass(frozen=True)
class JunkReportIntent:
    report_key: str
    message_key: str
    action: JunkReportAction
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
            "action": self.action.value,
            "approval_state": self.approval_state.value,
            "approval_required": True,
            "executable": False,
            "dispatched": False,
            "synthetic": True,
        }


def prepare_junk_report(
    fixture: OutlookMockFixture,
    request: JunkReportRequest,
    *,
    readiness: OutlookReadinessReport,
) -> JunkReportIntent:
    """Prepare a bounded classification report without dispatching it."""
    if not fixture.synthetic:
        raise ValueError("OUT-120 fixture execution requires synthetic=true")
    if not readiness.ready_for_readonly_discovery:
        raise ValueError("Outlook read-only discovery is not ready")
    if not any(item.message_key == request.message_key for item in fixture.messages):
        raise ValueError("synthetic message_key not found")

    action_key = "junk" if request.action is JunkReportAction.JUNK else "not-junk"
    intent = JunkReportIntent(
        report_key=f"report-{action_key}-{request.message_key}",
        message_key=request.message_key,
        action=request.action,
    )
    if intent.executable or intent.dispatched:
        raise RuntimeError("synthetic junk-report intent unexpectedly became executable")
    return intent


__all__ = [
    "JunkReportAction",
    "JunkReportIntent",
    "JunkReportRequest",
    "prepare_junk_report",
]
