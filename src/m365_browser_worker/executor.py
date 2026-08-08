"""Bounded serialized execution for one isolated browser profile."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import TypeVar

from planner_mcp.errors import WorkerBusy

T = TypeVar("T")


@dataclass(frozen=True)
class ExecutorSnapshot:
    """Content-free state suitable for health/readiness projection."""

    active: bool
    queued: int
    max_queue: int
    viable: bool

    def to_dict(self) -> dict[str, object]:
        return {
            "active": self.active,
            "queued": self.queued,
            "max_queue": self.max_queue,
            "viable": self.viable,
        }


class ProfileSerializedExecutor:
    """Allow one active operation and a bounded waiting queue per profile.

    ``asyncio.Lock`` is fair: waiters proceed in arrival order. Admission is
    bounded independently so overload fails immediately with ``WORKER_BUSY``
    rather than growing an unbounded queue.
    """

    def __init__(self, *, max_queue: int = 8) -> None:
        if max_queue < 0:
            raise ValueError("max_queue must be >= 0")
        self._max_queue = max_queue
        self._operation_lock = asyncio.Lock()
        self._state_lock = asyncio.Lock()
        self._admitted = 0
        self._active = False

    @property
    def viable(self) -> bool:
        """The serialization subsystem is configured and available."""
        return self._max_queue >= 0

    async def snapshot(self) -> ExecutorSnapshot:
        """Return bounded state without profile path or tenant/session content."""
        async with self._state_lock:
            queued = max(self._admitted - (1 if self._active else 0), 0)
            return ExecutorSnapshot(
                active=self._active,
                queued=queued,
                max_queue=self._max_queue,
                viable=self.viable,
            )

    async def execute(self, operation: str, work: Callable[[], Awaitable[T]]) -> T:
        """Run one operation under per-profile serialization.

        ``work`` is a factory so rejected requests cannot start side effects
        before admission has succeeded.
        """
        async with self._state_lock:
            capacity = self._max_queue + 1
            if self._admitted >= capacity:
                raise WorkerBusy(
                    "browser profile executor queue is full",
                    operation=operation,
                    max_queue=self._max_queue,
                )
            self._admitted += 1

        try:
            async with self._operation_lock:
                async with self._state_lock:
                    self._active = True
                try:
                    return await work()
                finally:
                    async with self._state_lock:
                        self._active = False
        finally:
            async with self._state_lock:
                self._admitted -= 1


__all__ = ["ExecutorSnapshot", "ProfileSerializedExecutor"]
