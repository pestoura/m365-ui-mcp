"""Synthetic OOO calendar-block state for OUT-133."""

from __future__ import annotations

from dataclasses import dataclass

from m365_mcp.apps.outlook.ooo_schedule import OooSchedule
from m365_mcp.apps.outlook.readiness import OutlookReadinessReport

_MAX_BLOCKS = 100


def _key(field: str, value: str) -> str:
    if not value or value != value.strip() or any(char.isspace() for char in value):
        raise ValueError(f"{field} must be a non-empty semantic token")
    if "@" in value or "://" in value or "/" in value:
        raise ValueError(f"{field} must not encode an address or URL")
    return value


@dataclass(frozen=True)
class OooCalendarBlock:
    block_key: str
    calendar_key: str
    schedule: OooSchedule
    show_as: str = "OOO"
    synthetic: bool = True
    live_support_state: str = "UNOBSERVED"

    def __post_init__(self) -> None:
        _key("block_key", self.block_key)
        _key("calendar_key", self.calendar_key)
        if self.show_as != "OOO":
            raise ValueError("OOO calendar block must use show_as=OOO")
        if not self.schedule.synthetic or self.schedule.live_support_state != "UNOBSERVED":
            raise ValueError("OOO block requires a synthetic relative schedule")
        if not self.synthetic or self.live_support_state != "UNOBSERVED":
            raise ValueError("OOO calendar block must remain synthetic and live-unobserved")


@dataclass(frozen=True)
class OooCalendarBlockResult:
    block_key: str
    changed: bool
    verified: bool
    read_back: OooCalendarBlock
    dispatched: bool = False
    synthetic: bool = True


def configure_ooo_calendar_block(
    blocks: tuple[OooCalendarBlock, ...],
    desired: OooCalendarBlock,
    *,
    readiness: OutlookReadinessReport,
) -> tuple[tuple[OooCalendarBlock, ...], OooCalendarBlockResult]:
    """Create/update one local synthetic OOO calendar block with exact read-back."""
    if not readiness.ready_for_readonly_discovery:
        raise ValueError("Outlook read-only discovery is not ready")
    if len(blocks) > _MAX_BLOCKS:
        raise ValueError("OOO calendar block catalog exceeds bounded size")
    keys = tuple(item.block_key for item in blocks)
    if len(keys) != len(set(keys)):
        raise ValueError("OOO calendar block catalog contains duplicate block_key")
    current = next((item for item in blocks if item.block_key == desired.block_key), None)
    if current is None and len(blocks) >= _MAX_BLOCKS:
        raise ValueError("OOO calendar block catalog is full")
    remaining = tuple(item for item in blocks if item.block_key != desired.block_key)
    updated = tuple(sorted(remaining + (desired,), key=lambda item: item.block_key))
    read_back = next(item for item in updated if item.block_key == desired.block_key)
    if read_back != desired:
        raise RuntimeError("OOO calendar block read-back did not prove requested state")
    result = OooCalendarBlockResult(
        block_key=desired.block_key,
        changed=current != desired,
        verified=True,
        read_back=read_back,
    )
    return updated, result


__all__ = ["OooCalendarBlock", "OooCalendarBlockResult", "configure_ooo_calendar_block"]
