"""Application-neutral Playwright persistent-browser boundary.

This module owns the browser/profile lifecycle primitives used by Microsoft 365
application adapters. It deliberately exposes no generic click/selector/script
surface and never exports authenticated session material.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from m365_browser_worker.egress import enforce_route_egress
from m365_mcp.config import browser_runtime_settings
from planner_mcp.errors import BlockerConditionalAccess, UiContractUnattested
from planner_mcp.ui_contract import load_status


@dataclass(frozen=True)
class BrowserConfig:
    """Configuration of the isolated professional browser profile."""

    profile_dir: Path
    headless: bool = True
    mode: str = "mock"

    @classmethod
    def from_env(cls) -> BrowserConfig:
        """Build configuration through the canonical M365/legacy alias policy."""
        profile_dir, headless, mode = browser_runtime_settings()
        return cls(profile_dir=profile_dir, headless=headless, mode=mode)

    @property
    def is_mock(self) -> bool:
        return self.mode.lower() == "mock"


CONDITIONAL_ACCESS_MARKERS = (
    "your device must be managed",
    "device is not compliant",
    "enrol this device",
    "enroll this device",
    "company portal",
)


def detect_conditional_access_block(page_text: str) -> bool:
    """Detect a Conditional Access managed-device wall from page text."""
    lowered = page_text.lower()
    return any(marker in lowered for marker in CONDITIONAL_ACCESS_MARKERS)


class PersistentBrowser:
    """Persistent-profile Chromium abstraction.

    The persistent profile is the authentication boundary. Passwords, cookies,
    tokens and storage state are never copied into MCP or application state.
    """

    def __init__(self, config: BrowserConfig | None = None) -> None:
        self.config = config or BrowserConfig.from_env()
        self._playwright: Any = None
        self._context: Any = None

    @property
    def started(self) -> bool:
        """Return whether this process currently owns a live Chromium context."""
        return self._context is not None and self._playwright is not None

    def ensure_live_allowed(self, operation: str) -> None:
        """Fail closed for semantic live operations without an attested UIContract."""
        status = load_status()
        if not status.attested:
            raise UiContractUnattested(
                f"live browser operation '{operation}' blocked",
                ui_contract_version=status.version,
            )

    async def start(self) -> None:
        """Launch and own Playwright plus the persistent Chromium context."""
        if self.config.is_mock:
            return
        if self.started:
            return
        if self._context is not None or self._playwright is not None:
            await self.stop()

        from playwright.async_api import async_playwright  # noqa: PLC0415

        playwright = await async_playwright().start()
        context: Any = None
        try:
            self.config.profile_dir.mkdir(parents=True, exist_ok=True)
            context = await playwright.chromium.launch_persistent_context(
                user_data_dir=str(self.config.profile_dir),
                headless=self.config.headless,
                args=["--no-first-run", "--no-default-browser-check"],
            )
            await context.route("**/*", enforce_route_egress)
        finally:
            if context is None:
                await playwright.stop()

        self._playwright = playwright
        self._context = context

    async def stop(self) -> None:
        """Close Chromium and Playwright deterministically, even after partial failure."""
        context = self._context
        playwright = self._playwright
        self._context = None
        self._playwright = None

        try:
            if context is not None:
                await context.close()
        finally:
            if playwright is not None:
                await playwright.stop()

    def guard_conditional_access(self, page_text: str) -> None:
        """Raise the fail-closed blocker when Conditional Access demands enrolment."""
        if detect_conditional_access_block(page_text):
            raise BlockerConditionalAccess(
                "Conditional Access requires a managed/compliant device; "
                "enrolment and bypass are forbidden by policy"
            )
