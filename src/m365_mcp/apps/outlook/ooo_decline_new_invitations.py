"""Governed synthetic OOO decline-new-invitations intent for OUT-134."""

from __future__ import annotations

from dataclasses import dataclass

from m365_mcp.apps.outlook.ooo_schedule import OooSchedule
from m365_mcp.apps.outlook.outbound_models import OutboundApprovalState
from m365_mcp.apps.outlook.readiness import OutlookReadinessReport


@dataclass(frozen=True)
class OooDeclineNewInvitationsIntent:
    policy_key: str
    schedule: OooSchedule
    enabled: bool
    approval_state: OutboundApprovalState = OutboundApprovalState.REQUIRED_NOT_BOUND
    dispatched: bool = False
    synthetic: bool = True
    live_support_state: str = "UNOBSERVED"

    def __post_init__(self) -> None:
        if not self.policy_key or self.policy_key != self.policy_key.strip():
            raise ValueError("policy_key must be a non-empty semantic token")
        invalid_key = (
            any(char.isspace() for char in self.policy_key)
            or "@" in self.policy_key
            or "://" in self.policy_key
        )
        if invalid_key:
            raise ValueError("policy_key must be opaque and must not encode an address or URL")
        if not self.schedule.synthetic or self.schedule.live_support_state != "UNOBSERVED":
            raise ValueError("decline-new-invitations requires a synthetic relative schedule")
        if not self.synthetic or self.live_support_state != "UNOBSERVED":
            raise ValueError("OOO decline intent must remain synthetic and live-unobserved")

    @property
    def executable(self) -> bool:
        return False

    def to_projection(self) -> dict[str, object]:
        return {
            "policy_key": self.policy_key,
            "enabled": self.enabled,
            "approval_state": self.approval_state.value,
            "approval_required": True,
            "executable": False,
            "dispatched": False,
            "synthetic": True,
            "live_support_state": self.live_support_state,
        }


def prepare_ooo_decline_new_invitations(
    *,
    policy_key: str,
    schedule: OooSchedule,
    enabled: bool,
    readiness: OutlookReadinessReport,
) -> OooDeclineNewInvitationsIntent:
    """Prepare policy intent only; never decline an invitation in synthetic mode."""
    if not readiness.ready_for_readonly_discovery:
        raise ValueError("Outlook read-only discovery is not ready")
    intent = OooDeclineNewInvitationsIntent(policy_key, schedule, enabled)
    if intent.executable or intent.dispatched:
        raise RuntimeError("synthetic OOO decline intent unexpectedly became executable")
    return intent


__all__ = ["OooDeclineNewInvitationsIntent", "prepare_ooo_decline_new_invitations"]
