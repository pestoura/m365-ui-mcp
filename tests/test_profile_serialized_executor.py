from __future__ import annotations

import asyncio

import pytest

from m365_browser_worker.executor import ProfileSerializedExecutor
from planner_mcp.errors import WorkerBusy


async def test_executor_never_overlaps_profile_operations() -> None:
    executor = ProfileSerializedExecutor(max_queue=4)
    active = 0
    max_active = 0
    order: list[int] = []

    async def work(index: int) -> int:
        nonlocal active, max_active
        active += 1
        max_active = max(max_active, active)
        order.append(index)
        await asyncio.sleep(0)
        active -= 1
        return index

    tasks = [
        asyncio.create_task(executor.execute(f"op-{index}", lambda i=index: work(i)))
        for index in range(3)
    ]
    assert await asyncio.gather(*tasks) == [0, 1, 2]
    assert max_active == 1
    assert order == [0, 1, 2]


async def test_queue_overflow_fails_closed_with_worker_busy() -> None:
    executor = ProfileSerializedExecutor(max_queue=1)
    release = asyncio.Event()
    started = asyncio.Event()

    async def blocked() -> str:
        started.set()
        await release.wait()
        return "done"

    first = asyncio.create_task(executor.execute("first", blocked))
    await started.wait()
    second = asyncio.create_task(executor.execute("second", blocked))
    await asyncio.sleep(0)

    snapshot = await executor.snapshot()
    assert snapshot.active is True
    assert snapshot.queued == 1

    with pytest.raises(WorkerBusy) as exc_info:
        await executor.execute("third", blocked)
    assert exc_info.value.code == "WORKER_BUSY"
    assert exc_info.value.context == {"operation": "third", "max_queue": 1}

    release.set()
    assert await first == "done"
    assert await second == "done"


async def test_cancelled_waiter_releases_admission_capacity() -> None:
    executor = ProfileSerializedExecutor(max_queue=1)
    release = asyncio.Event()
    started = asyncio.Event()

    async def first_work() -> str:
        started.set()
        await release.wait()
        return "first"

    async def immediate() -> str:
        return "next"

    first = asyncio.create_task(executor.execute("first", first_work))
    await started.wait()
    waiter = asyncio.create_task(executor.execute("cancel-me", immediate))
    await asyncio.sleep(0)
    waiter.cancel()
    with pytest.raises(asyncio.CancelledError):
        await waiter

    replacement = asyncio.create_task(executor.execute("replacement", immediate))
    await asyncio.sleep(0)
    snapshot = await executor.snapshot()
    assert snapshot.queued == 1

    release.set()
    assert await first == "first"
    assert await replacement == "next"
    final = await executor.snapshot()
    assert final.active is False
    assert final.queued == 0


async def test_failed_operation_releases_executor() -> None:
    executor = ProfileSerializedExecutor(max_queue=0)

    async def fail() -> None:
        raise RuntimeError("boom")

    with pytest.raises(RuntimeError, match="boom"):
        await executor.execute("fail", fail)

    async def recover() -> str:
        return "ok"

    assert await executor.execute("recover", recover) == "ok"
    snapshot = await executor.snapshot()
    assert snapshot.active is False
    assert snapshot.queued == 0
    assert snapshot.viable is True


def test_negative_queue_capacity_is_rejected() -> None:
    with pytest.raises(ValueError, match="max_queue must be >= 0"):
        ProfileSerializedExecutor(max_queue=-1)
