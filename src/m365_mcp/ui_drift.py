"""Closed UI drift lifecycle for capability-scoped UIContract evidence."""

from __future__ import annotations

from enum import StrEnum


class UILifecycleState(StrEnum):
    """Lifecycle states for already-classified UI evidence."""

    HEALTHY = "HEALTHY"
    STALE = "STALE"
    DRIFTED = "DRIFTED"
    RE_ATTESTATION_REQUIRED = "RE_ATTESTATION_REQUIRED"


class UILifecycleEvent(StrEnum):
    """Closed events that may move UI evidence between lifecycle states."""

    EVIDENCE_STALE = "EVIDENCE_STALE"
    DRIFT_DETECTED = "DRIFT_DETECTED"
    REATTESTATION_REQUIRED = "REATTESTATION_REQUIRED"
    REATTESTATION_PASSED = "REATTESTATION_PASSED"


_TRANSITIONS: dict[tuple[UILifecycleState, UILifecycleEvent], UILifecycleState] = {
    (UILifecycleState.HEALTHY, UILifecycleEvent.EVIDENCE_STALE): UILifecycleState.STALE,
    (UILifecycleState.HEALTHY, UILifecycleEvent.DRIFT_DETECTED): UILifecycleState.DRIFTED,
    (
        UILifecycleState.HEALTHY,
        UILifecycleEvent.REATTESTATION_REQUIRED,
    ): UILifecycleState.RE_ATTESTATION_REQUIRED,
    (UILifecycleState.STALE, UILifecycleEvent.EVIDENCE_STALE): UILifecycleState.STALE,
    (UILifecycleState.STALE, UILifecycleEvent.DRIFT_DETECTED): UILifecycleState.DRIFTED,
    (
        UILifecycleState.STALE,
        UILifecycleEvent.REATTESTATION_REQUIRED,
    ): UILifecycleState.RE_ATTESTATION_REQUIRED,
    (UILifecycleState.STALE, UILifecycleEvent.REATTESTATION_PASSED): UILifecycleState.HEALTHY,
    (UILifecycleState.DRIFTED, UILifecycleEvent.DRIFT_DETECTED): UILifecycleState.DRIFTED,
    (
        UILifecycleState.DRIFTED,
        UILifecycleEvent.REATTESTATION_REQUIRED,
    ): UILifecycleState.RE_ATTESTATION_REQUIRED,
    (
        UILifecycleState.RE_ATTESTATION_REQUIRED,
        UILifecycleEvent.REATTESTATION_REQUIRED,
    ): UILifecycleState.RE_ATTESTATION_REQUIRED,
    (
        UILifecycleState.RE_ATTESTATION_REQUIRED,
        UILifecycleEvent.DRIFT_DETECTED,
    ): UILifecycleState.DRIFTED,
    (
        UILifecycleState.RE_ATTESTATION_REQUIRED,
        UILifecycleEvent.REATTESTATION_PASSED,
    ): UILifecycleState.HEALTHY,
}


def transition_ui_lifecycle(
    current: UILifecycleState,
    event: UILifecycleEvent,
) -> UILifecycleState:
    """Apply one closed lifecycle transition, rejecting unsafe shortcuts."""
    try:
        return _TRANSITIONS[(current, event)]
    except KeyError as exc:
        raise ValueError(
            f"invalid UI lifecycle transition: {current.value} + {event.value}"
        ) from exc


def degrades_capability(state: UILifecycleState) -> bool:
    """Return whether the lifecycle state must withdraw effective support."""
    return state in {
        UILifecycleState.STALE,
        UILifecycleState.DRIFTED,
        UILifecycleState.RE_ATTESTATION_REQUIRED,
    }


__all__ = [
    "UILifecycleEvent",
    "UILifecycleState",
    "degrades_capability",
    "transition_ui_lifecycle",
]
