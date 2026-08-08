"""CORE-027 operation-scoped page lifecycle isolation tests."""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from m365_browser_worker.browser import BrowserConfig, PersistentBrowser
from planner_mcp.errors import WorkerUnavailable


class RecordingPage:
    def __init__(self, number: int) -> None:
        self.number = number
        self.closed = False
        self.local_state: dict[str, object] = {}

    async def close(self) -> None:
        self.closed = True


class RecordingContext:
    def __init__(self) -> None:
        self.pages: list[RecordingPage] = []

    async def new_page(self) -> RecordingPage:
        page = RecordingPage(len(self.pages) + 1)
        self.pages.append(page)
        return page


class RecordingPlaywright:
    pass


def _started_browser(tmp_path: Path, context: RecordingContext) -> PersistentBrowser:
    browser = PersistentBrowser(BrowserConfig(profile_dir=tmp_path, mode="live"))
    browser._playwright = RecordingPlaywright()
    browser._context = context
    return browser


async def test_sequential_operations_receive_fresh_pages_without_local_state_bleed(
    tmp_path: Path,
) -> None:
    context = RecordingContext()
    browser = _started_browser(tmp_path, context)

    async with browser.operation_page("planner.plan.list") as first:
        first.local_state["operation_marker"] = "first"
        assert first.closed is False

    async with browser.operation_page("planner.task.list") as second:
        assert second.local_state == {}
        assert second.closed is False

    assert first is not second
    assert [page.number for page in context.pages] == [1, 2]
    assert all(page.closed for page in context.pages)


async def test_operation_page_closes_after_operation_failure(tmp_path: Path) -> None:
    context = RecordingContext()
    browser = _started_browser(tmp_path, context)

    with pytest.raises(RuntimeError, match="synthetic operation failure"):
        async with browser.operation_page("planner.plan.get"):
            raise RuntimeError("synthetic operation failure")

    assert len(context.pages) == 1
    assert context.pages[0].closed is True


async def test_operation_page_closes_after_cancellation(tmp_path: Path) -> None:
    context = RecordingContext()
    browser = _started_browser(tmp_path, context)
    entered = asyncio.Event()
    hold = asyncio.Event()

    async def operation() -> None:
        async with browser.operation_page("planner.task.get"):
            entered.set()
            await hold.wait()

    task = asyncio.create_task(operation())
    await entered.wait()
    task.cancel()

    with pytest.raises(asyncio.CancelledError):
        await task

    assert len(context.pages) == 1
    assert context.pages[0].closed is True


async def test_operation_page_fails_closed_without_owned_browser_context(
    tmp_path: Path,
) -> None:
    browser = PersistentBrowser(BrowserConfig(profile_dir=tmp_path, mode="live"))

    with pytest.raises(WorkerUnavailable) as exc_info:
        async with browser.operation_page("planner.plan.list"):
            pytest.fail("operation page yielded without a browser context")

    assert exc_info.value.code == "WORKER_UNAVAILABLE"
    assert exc_info.value.context == {"operation": "planner.plan.list"}
