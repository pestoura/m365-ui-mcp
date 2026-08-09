"""Synthetic-only Outlook My Day / smart-list reads for OUT-029."""
from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from m365_mcp.apps.outlook.mock_ui import OutlookMockFixture
from m365_mcp.apps.outlook.readiness import OutlookReadinessReport


class SmartListKind(StrEnum):
    MY_DAY = "MY_DAY"
    IMPORTANT = "IMPORTANT"
    PLANNED = "PLANNED"
    COMPLETED = "COMPLETED"


@dataclass(frozen=True)
class SyntheticSmartTask:
    task_key: str
    title: str
    important: bool = False
    completed: bool = False
    planned_day_offset: int | None = None
    my_day: bool = False

    def __post_init__(self) -> None:
        if not self.task_key or self.task_key != self.task_key.strip() or "@" in self.task_key:
            raise ValueError("task_key must be opaque")
        if not self.title or self.title != self.title.strip():
            raise ValueError("title must be non-empty and trimmed")
        if self.planned_day_offset is not None and (isinstance(self.planned_day_offset, bool) or not -3650 <= self.planned_day_offset <= 3650):
            raise ValueError("planned_day_offset must be bounded")

    def to_projection(self) -> dict[str, object]:
        return {"task_key": self.task_key, "title": self.title, "important": self.important, "completed": self.completed, "planned_day_offset": self.planned_day_offset, "my_day": self.my_day, "synthetic": True}


def default_synthetic_smart_tasks() -> tuple[SyntheticSmartTask, ...]:
    return (
        SyntheticSmartTask("smart-alpha", "Review synthetic item", important=True, planned_day_offset=0, my_day=True),
        SyntheticSmartTask("smart-bravo", "Prepare synthetic note", planned_day_offset=2),
        SyntheticSmartTask("smart-charlie", "Closed synthetic task", completed=True, planned_day_offset=-1),
    )


def _gate(fixture: OutlookMockFixture, readiness: OutlookReadinessReport) -> None:
    if not fixture.synthetic:
        raise ValueError("OUT-029 fixture execution requires synthetic=true")
    if not readiness.ready_for_readonly_discovery:
        raise ValueError("Outlook read-only discovery is not ready")


def read_fixture_smart_list(fixture: OutlookMockFixture, kind: SmartListKind, *, readiness: OutlookReadinessReport, reference_day_offset: int = 0, tasks: tuple[SyntheticSmartTask, ...] | None = None) -> tuple[SyntheticSmartTask, ...]:
    _gate(fixture, readiness)
    if not isinstance(kind, SmartListKind):
        raise ValueError("kind must be a closed SmartListKind")
    if isinstance(reference_day_offset, bool) or not -3650 <= reference_day_offset <= 3650:
        raise ValueError("reference_day_offset must be bounded")
    catalog = default_synthetic_smart_tasks() if tasks is None else tasks
    keys = tuple(item.task_key for item in catalog)
    if len(set(keys)) != len(keys):
        raise ValueError("smart-list task keys must be unique")
    if kind is SmartListKind.MY_DAY:
        return tuple(item for item in catalog if item.my_day and not item.completed)
    if kind is SmartListKind.IMPORTANT:
        return tuple(item for item in catalog if item.important and not item.completed)
    if kind is SmartListKind.PLANNED:
        return tuple(item for item in catalog if item.planned_day_offset is not None and item.planned_day_offset >= reference_day_offset and not item.completed)
    return tuple(item for item in catalog if item.completed)


__all__ = ["SmartListKind", "SyntheticSmartTask", "default_synthetic_smart_tasks", "read_fixture_smart_list"]
