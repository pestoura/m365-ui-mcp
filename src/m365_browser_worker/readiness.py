"""Fail-closed liveness/readiness projection for the M365 browser worker."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from planner_mcp.auth import AuthState


class ReadinessReason(StrEnum):
    """Closed reasons why live Microsoft 365 readiness is not proven."""

    BROWSER_NOT_STARTED = "BROWSER_NOT_STARTED"
    PROFILE_UNAVAILABLE = "PROFILE_UNAVAILABLE"
    AUTH_NOT_AUTHENTICATED = "AUTH_NOT_AUTHENTICATED"
    UI_CONTRACT_UNATTESTED = "UI_CONTRACT_UNATTESTED"
    BROKER_UNAVAILABLE = "BROKER_UNAVAILABLE"
    PROTOCOL_INCOMPATIBLE = "PROTOCOL_INCOMPATIBLE"
    LOCK_UNAVAILABLE = "LOCK_UNAVAILABLE"


@dataclass(frozen=True)
class WorkerReadiness:
    """One content-free readiness projection for live Microsoft 365 work."""

    browser_started: bool
    profile_usable: bool
    auth_state: AuthState
    ui_contract_attested: bool
    broker_viable: bool
    protocol_compatible: bool
    lock_viable: bool
    reasons: tuple[ReadinessReason, ...]

    @property
    def ready(self) -> bool:
        return not self.reasons

    def to_dict(self) -> dict[str, object]:
        return {
            "ready": self.ready,
            "target": "live_m365",
            "browser_started": self.browser_started,
            "profile_usable": self.profile_usable,
            "auth_state": self.auth_state.value,
            "ui_contract_attested": self.ui_contract_attested,
            "broker_viable": self.broker_viable,
            "protocol_compatible": self.protocol_compatible,
            "lock_viable": self.lock_viable,
            "reasons": [reason.value for reason in self.reasons],
        }


def evaluate_worker_readiness(
    *,
    browser_started: bool,
    profile_usable: bool,
    auth_state: AuthState | str,
    ui_contract_attested: bool,
    broker_viable: bool,
    protocol_compatible: bool,
    lock_viable: bool,
) -> WorkerReadiness:
    """Require all live subsystems explicitly; absence is never inferred as support."""
    state = AuthState(auth_state)
    reasons: list[ReadinessReason] = []
    if not browser_started:
        reasons.append(ReadinessReason.BROWSER_NOT_STARTED)
    if not profile_usable:
        reasons.append(ReadinessReason.PROFILE_UNAVAILABLE)
    if state is not AuthState.AUTHENTICATED:
        reasons.append(ReadinessReason.AUTH_NOT_AUTHENTICATED)
    if not ui_contract_attested:
        reasons.append(ReadinessReason.UI_CONTRACT_UNATTESTED)
    if not broker_viable:
        reasons.append(ReadinessReason.BROKER_UNAVAILABLE)
    if not protocol_compatible:
        reasons.append(ReadinessReason.PROTOCOL_INCOMPATIBLE)
    if not lock_viable:
        reasons.append(ReadinessReason.LOCK_UNAVAILABLE)
    return WorkerReadiness(
        browser_started=browser_started,
        profile_usable=profile_usable,
        auth_state=state,
        ui_contract_attested=ui_contract_attested,
        broker_viable=broker_viable,
        protocol_compatible=protocol_compatible,
        lock_viable=lock_viable,
        reasons=tuple(reasons),
    )


__all__ = ["ReadinessReason", "WorkerReadiness", "evaluate_worker_readiness"]
