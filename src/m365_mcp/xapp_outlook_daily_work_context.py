"""Synthetic-only bounded Outlook daily work context for XAPP-023."""

from __future__ import annotations

from dataclasses import dataclass

from m365_mcp.apps.outlook.calendar_events import EventProjection
from m365_mcp.apps.outlook.todo_task_reads import SyntheticTodoTask, TaskState
from m365_mcp.xapp_outlook_inbox_digest import OutlookInboxDigest

_MAX_KEYS = 100
_MIN_DAY_OFFSET = -3650
_MAX_DAY_OFFSET = 3650


@dataclass(frozen=True)
class OutlookDailyWorkContext:
    day_offset: int
    unread_mail_count: int
    attachment_mail_count: int
    event_keys: tuple[str, ...]
    open_task_keys: tuple[str, ...]
    synthetic: bool = True
    live_observed: bool = False
    execution_performed: bool = False

    def __post_init__(self) -> None:
        if not _MIN_DAY_OFFSET <= self.day_offset <= _MAX_DAY_OFFSET:
            raise ValueError("day_offset exceeds bounded window")
        if min(self.unread_mail_count, self.attachment_mail_count) < 0:
            raise ValueError("mail counts must be non-negative")
        for keys in (self.event_keys, self.open_task_keys):
            if len(keys) > _MAX_KEYS or len(keys) != len(set(keys)):
                raise ValueError("daily work keys must be unique and bounded")
            if any(not key or "@" in key or "://" in key for key in keys):
                raise ValueError("daily work keys must remain opaque")
        if not self.synthetic or self.live_observed or self.execution_performed:
            raise ValueError("daily work context must remain synthetic and non-executing")


def build_synthetic_daily_work_context(
    digest: OutlookInboxDigest,
    events: tuple[EventProjection, ...],
    tasks: tuple[SyntheticTodoTask, ...],
    *,
    day_offset: int = 0,
) -> OutlookDailyWorkContext:
    """Reduce existing synthetic projections to one bounded work-context view."""
    if not digest.synthetic or digest.live_observed or digest.execution_performed:
        raise ValueError("XAPP-023 requires a synthetic non-executing inbox digest")
    event_keys = tuple(
        sorted(
            event.event_key
            for event in events
            if event.synthetic
            and not event.is_cancelled
            and event.start_day_offset == day_offset
        )
    )
    open_task_keys = tuple(
        sorted(
            task.task_key
            for task in tasks
            if task.state is not TaskState.COMPLETED
            and task.due_day_offset is not None
            and task.due_day_offset <= day_offset
        )
    )
    return OutlookDailyWorkContext(
        day_offset=day_offset,
        unread_mail_count=digest.unread_count,
        attachment_mail_count=digest.attachment_count,
        event_keys=event_keys,
        open_task_keys=open_task_keys,
    )


__all__ = ["OutlookDailyWorkContext", "build_synthetic_daily_work_context"]
