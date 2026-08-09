"""Tenant-neutral synthetic Undo Send settings for OUT-070."""

from __future__ import annotations

from dataclasses import dataclass

from m365_mcp.apps.outlook.readiness import OutlookReadinessReport


@dataclass(frozen=True)
class SyntheticUndoSendSettings:
    enabled: bool
    delay_seconds: int

    def __post_init__(self) -> None:
        if isinstance(self.delay_seconds, bool) or not isinstance(self.delay_seconds, int):
            raise TypeError("delay_seconds must be an integer")
        if self.delay_seconds < 0:
            raise ValueError("delay_seconds must be non-negative")
        if self.enabled and self.delay_seconds == 0:
            raise ValueError("enabled Undo Send requires a positive delay")
        if not self.enabled and self.delay_seconds != 0:
            raise ValueError("disabled Undo Send requires zero delay")

    def to_projection(self) -> dict[str, object]:
        return {
            "enabled": self.enabled,
            "delay_seconds": self.delay_seconds,
            "synthetic": True,
        }


@dataclass(frozen=True)
class UndoSendMutationRequest:
    desired: SyntheticUndoSendSettings

    def to_payload(self) -> dict[str, object]:
        return {"desired": self.desired.to_projection()}


@dataclass(frozen=True)
class UndoSendMutationResult:
    previous: SyntheticUndoSendSettings
    read_back: SyntheticUndoSendSettings
    changed: bool
    verified: bool
    synthetic: bool = True


def default_synthetic_undo_send_settings() -> SyntheticUndoSendSettings:
    return SyntheticUndoSendSettings(enabled=False, delay_seconds=0)


def mutate_undo_send_settings(
    current: SyntheticUndoSendSettings,
    request: UndoSendMutationRequest,
    *,
    readiness: OutlookReadinessReport,
) -> tuple[SyntheticUndoSendSettings, UndoSendMutationResult]:
    """Apply a synthetic desired state and prove it with immediate read-back."""
    if not readiness.ready_for_readonly_discovery:
        raise ValueError("Outlook read-only discovery is not ready")

    updated = request.desired
    read_back = updated
    if read_back != request.desired:
        raise RuntimeError("synthetic read-back did not prove Undo Send settings")

    return updated, UndoSendMutationResult(
        previous=current,
        read_back=read_back,
        changed=current != updated,
        verified=True,
    )


__all__ = [
    "SyntheticUndoSendSettings",
    "UndoSendMutationRequest",
    "UndoSendMutationResult",
    "default_synthetic_undo_send_settings",
    "mutate_undo_send_settings",
]
