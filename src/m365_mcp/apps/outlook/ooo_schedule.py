"""Synthetic relative out-of-office schedule configuration for OUT-132."""

from __future__ import annotations

from dataclasses import dataclass

from m365_mcp.apps.outlook.readiness import OutlookReadinessReport


_MAX_WEEK_MINUTES = 7 * 24 * 60
_SLOT_MINUTES = 15


@dataclass(frozen=True)
class OooSchedule:
    start_minute: int
    end_minute: int
    anchor: str = "SYNTHETIC_WEEK"
    synthetic: bool = True
    live_support_state: str = "UNOBSERVED"

    def __post_init__(self) -> None:
        if not (0 <= self.start_minute < self.end_minute <= _MAX_WEEK_MINUTES):
            raise ValueError("OOO schedule must be a bounded increasing relative window")
        if self.start_minute % _SLOT_MINUTES or self.end_minute % _SLOT_MINUTES:
            raise ValueError("OOO schedule must use 15-minute synthetic slots")
        if self.anchor != "SYNTHETIC_WEEK":
            raise ValueError("OOO schedule must not encode a real timestamp or tenant timezone")
        if not self.synthetic or self.live_support_state != "UNOBSERVED":
            raise ValueError("OOO schedule must remain synthetic and live-unobserved")


@dataclass(frozen=True)
class OooScheduleResult:
    changed: bool
    read_back: OooSchedule
    verified: bool = True
    dispatched: bool = False
    synthetic: bool = True


def configure_ooo_schedule(
    current: OooSchedule,
    desired: OooSchedule,
    *,
    readiness: OutlookReadinessReport,
) -> tuple[OooSchedule, OooScheduleResult]:
    """Configure a relative synthetic schedule; never bind a live calendar window."""
    if not readiness.ready_for_readonly_discovery:
        raise ValueError("Outlook read-only discovery is not ready")
    if desired.anchor != "SYNTHETIC_WEEK" or not desired.synthetic:
        raise ValueError("synthetic relative OOO schedule is required")
    result = OooScheduleResult(changed=desired != current, read_back=desired)
    if result.dispatched or not result.verified:
        raise RuntimeError("OOO schedule configuration failed closed")
    return desired, result


__all__ = [
    "OooSchedule",
    "OooScheduleResult",
    "configure_ooo_schedule",
]
