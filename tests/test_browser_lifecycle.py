"""CORE-021 FastAPI ownership of Playwright/Chromium lifecycle."""

from __future__ import annotations

from pathlib import Path

import pytest

from m365_browser_worker import lifecycle
from m365_browser_worker.browser import BrowserConfig, PersistentBrowser
from planner_browser_worker.app import create_app


class RecordingBrowser(PersistentBrowser):
    def __init__(self, *, fail_start: bool = False) -> None:
        super().__init__(
            BrowserConfig(profile_dir=Path.cwd() / ".core-021-test", mode="mock")
        )
        self.fail_start = fail_start
        self.start_calls = 0
        self.stop_calls = 0

    async def start(self) -> None:
        self.start_calls += 1
        if self.fail_start:
            raise RuntimeError("synthetic startup failure")

    async def stop(self) -> None:
        self.stop_calls += 1


class RecordingContext:
    def __init__(self, *, fail_close: bool = False) -> None:
        self.fail_close = fail_close
        self.close_calls = 0

    async def close(self) -> None:
        self.close_calls += 1
        if self.fail_close:
            raise RuntimeError("synthetic context close failure")


class RecordingPlaywright:
    def __init__(self) -> None:
        self.stop_calls = 0

    async def stop(self) -> None:
        self.stop_calls += 1


async def test_fastapi_lifespan_starts_and_stops_injected_browser_once() -> None:
    browser = RecordingBrowser()
    app = create_app(browser)

    assert browser.start_calls == 0
    assert browser.stop_calls == 0

    async with app.router.lifespan_context(app):
        assert browser.start_calls == 1
        assert browser.stop_calls == 0
        assert app.state.browser is browser

    assert browser.start_calls == 1
    assert browser.stop_calls == 1


async def test_fastapi_lifespan_cleans_up_after_startup_failure() -> None:
    browser = RecordingBrowser(fail_start=True)
    app = create_app(browser)

    with pytest.raises(RuntimeError, match="synthetic startup failure"):
        async with app.router.lifespan_context(app):
            pytest.fail("lifespan yielded after startup failure")

    assert browser.start_calls == 1
    assert browser.stop_calls == 1


async def test_mock_browser_lifecycle_performs_no_playwright_work(tmp_path: Path) -> None:
    browser = PersistentBrowser(BrowserConfig(profile_dir=tmp_path, mode="mock"))

    await browser.start()
    assert browser.started is False
    assert browser._playwright is None
    assert browser._context is None

    await browser.stop()
    assert browser.started is False


async def test_live_start_is_idempotent_when_process_already_owns_context(tmp_path: Path) -> None:
    browser = PersistentBrowser(BrowserConfig(profile_dir=tmp_path, mode="live"))
    playwright = RecordingPlaywright()
    context = RecordingContext()
    browser._playwright = playwright
    browser._context = context

    await browser.start()

    assert browser._playwright is playwright
    assert browser._context is context
    assert context.close_calls == 0
    assert playwright.stop_calls == 0


async def test_stop_closes_context_and_playwright_and_resets_ownership(tmp_path: Path) -> None:
    browser = PersistentBrowser(BrowserConfig(profile_dir=tmp_path, mode="live"))
    playwright = RecordingPlaywright()
    context = RecordingContext()
    browser._playwright = playwright
    browser._context = context

    await browser.stop()

    assert context.close_calls == 1
    assert playwright.stop_calls == 1
    assert browser.started is False
    assert browser._context is None
    assert browser._playwright is None


async def test_stop_still_stops_playwright_when_context_close_fails(tmp_path: Path) -> None:
    browser = PersistentBrowser(BrowserConfig(profile_dir=tmp_path, mode="live"))
    playwright = RecordingPlaywright()
    context = RecordingContext(fail_close=True)
    browser._playwright = playwright
    browser._context = context

    with pytest.raises(RuntimeError, match="synthetic context close failure"):
        await browser.stop()

    assert context.close_calls == 1
    assert playwright.stop_calls == 1
    assert browser.started is False
    assert browser._context is None
    assert browser._playwright is None


def test_lifecycle_surface_contains_no_generic_browser_primitive() -> None:
    forbidden = {
        "browser_exec",
        "javascript",
        "xpath",
        "raw_action",
        "storage_state",
    }
    exported = set(lifecycle.__all__)
    assert not (forbidden & exported)
