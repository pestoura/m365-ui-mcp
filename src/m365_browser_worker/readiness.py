"""Fail-closed liveness/readiness projection for the M365 browser worker."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from planner_mcp.auth import AuthState


class ReadinessReason(StrEnum):
    """Closed reasons why live Microsoft 365 readiness is not proven."""

    BROWSER_NOT_STARTED = "BROWSER_NOT_STARTED"
    AUTH_NOT_AUTHENTICATED = "AUTH_NOT_AUTHENTICATED"
    UI_CONTRACT_UNATTESTED = "UI_CONTRACT_UNATTESTED"
    BROKER_UNAVAILABLE = "BROKER_UNAVAILABLE"


@dataclass(frozen=True)
class WorkerReadiness:
    """One content-free readiness projection for live Microsoft 365 work."""

    browser_started: bool
    auth_state: AuthState
    ui_contract_attested: bool
    broker_viable: bool
    reasons: tuple[ReadinessReason, ...]

    @property
    def ready(self) -> bool:
        return not self.reasons

    def to_dict(self) -> dict[str, object]:
        return {
            "ready": self.ready,
            "target": "live_m365",
            "browser_started": self.browser_started,
            "auth_state": self.auth_state.value,
            "ui_contract_attested": self.ui_contract_attested,
            "broker_viable": self.broker_viable,
            "reasons": [reason.value for reason in self.reasons],
        }


def evaluate_worker_readiness(
    *,
    browser_started: bool,
    auth_state: AuthState | str,
    ui_contract_attested: bool,
    broker_viable: bool,
) -> WorkerReadiness:
    """Require browser, auth, UI contract and broker viability without inference."""
    state = AuthState(auth_state)
    reasons: list[ReadinessReason] = []
    if not browser_started:
        reasons.append(ReadinessReason.BROWSER_NOT_STARTED)
    if state is not AuthState.AUTHENTICATED:
        reasons.append(ReadinessReason.AUTH_NOT_AUTHENTICATED)
    if not ui_contract_attested:
        reasons.append(ReadinessReason.UI_CONTRACT_UNATTESTED)
    if not broker_viable:
        reasons.append(ReadinessReason.BROKER_UNAVAILABLE)
    return WorkerReadiness(
        browser_started=browser_started,
        auth_state=state,
        ui_contract_attested=ui_contract_attested,
        broker_viable=broker_viable,
        reasons=tuple(reasons),
    )


__all__ = ["ReadinessReason", "WorkerReadiness", "evaluate_worker_readiness"]
