"""Fail-closed synthetic recall intent preparation for OUT-056."""

from __future__ import annotations

from dataclasses import dataclass

from m365_mcp.apps.outlook.mock_ui import OutlookMockFixture
from m365_mcp.apps.outlook.outbound_models import OutboundApprovalState
from m365_mcp.apps.outlook.readiness import OutlookReadinessReport


def _semantic_token(value: str, name: str) -> str:
    if not value or value != value.strip() or any(char.isspace() for char in value):
        raise ValueError(f"{name} must be a non-empty semantic token")
    return value


@dataclass(frozen=True)
class SyntheticRecallIntent:
    """Tenant-neutral recall preparation that can never execute by itself."""

    intent_key: str
    sent_message_key: str
    approval_state: OutboundApprovalState = OutboundApprovalState.REQUIRED_NOT_BOUND
    synthetic: bool = True

    def __post_init__(self) -> None:
        _semantic_token(self.intent_key, "intent_key")
        _semantic_token(self.sent_message_key, "sent_message_key")
        if not self.synthetic:
            raise ValueError("recall foundation is synthetic-only")
        if self.approval_state is not OutboundApprovalState.REQUIRED_NOT_BOUND:
            raise ValueError("recall approval cannot be pre-bound before tool registration")

    @property
    def executable(self) -> bool:
        return False

    def to_projection(self) -> dict[str, object]:
        return {
            "intent_key": self.intent_key,
            "sent_message_key": self.sent_message_key,
            "approval_state": self.approval_state.value,
            "approval_required": True,
            "executable": False,
            "synthetic": True,
        }


def prepare_recall_intent(
    fixture: OutlookMockFixture,
    *,
    intent_key: str,
    sent_message_key: str,
    readiness: OutlookReadinessReport,
) -> SyntheticRecallIntent:
    """Prepare recall only for a known synthetic message in the sent folder."""
    if not readiness.ready_for_readonly_discovery:
        raise ValueError("Outlook read-only discovery is not ready")
    if not fixture.synthetic:
        raise ValueError("OUT-056 requires synthetic source fixture")
    source = next(
        (item for item in fixture.messages if item.message_key == sent_message_key),
        None,
    )
    if source is None:
        raise ValueError("synthetic sent_message_key not found")
    if source.folder_key != "sent":
        raise ValueError("recall source must be a synthetic sent item")
    return SyntheticRecallIntent(
        intent_key=intent_key,
        sent_message_key=sent_message_key,
    )


def require_recall_execution_blocked(intent: SyntheticRecallIntent) -> None:
    """Prove recall remains blocked until semantic tooling and HITL exist."""
    if not intent.synthetic or intent.executable:
        raise RuntimeError("recall intent unexpectedly became executable")
    raise PermissionError(
        "recall execution blocked: semantic tool registration and canonical HITL approval required"
    )


__all__ = [
    "SyntheticRecallIntent",
    "prepare_recall_intent",
    "require_recall_execution_blocked",
]
