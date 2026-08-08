"""Playwright persistent Chromium profile abstraction.

Live mode never fabricates selectors: it fails closed until the UIContract is
attested, and it never performs device enrolment or Conditional Access bypass.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

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
        """Build the configuration from environment variables."""
        return cls(
            profile_dir=Path(
                os.getenv("PLANNER_BROWSER_PROFILE_DIR", "/var/lib/planner-worker/profile")
            ),
            headless=os.getenv("PLANNER_BROWSER_HEADLESS", "1") != "0",
            mode=os.getenv("PLANNER_MODE", "mock"),
        )

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

    The persistent profile IS the authentication mechanism: no passwords,
    cookies or tokens are ever read into worker or MCP state.
    """

    def __init__(self, config: BrowserConfig | None = None) -> None:
        self.config = config or BrowserConfig.from_env()
        self._context: Any = None

    def ensure_live_allowed(self, operation: str) -> None:
        """Fail closed for live operations without an attested UIContract."""
        status = load_status()
        if not status.attested:
            raise UiContractUnattested(
                f"live browser operation '{operation}' blocked",
                ui_contract_version=status.version,
            )

    async def start(self) -> None:
        """Launch the persistent Chromium context (live mode only)."""
        if self.config.is_mock:
            return
        self.ensure_live_allowed("start")
        from playwright.async_api import async_playwright  # noqa: PLC0415

        playwright = await async_playwright().start()
        self.config.profile_dir.mkdir(parents=True, exist_ok=True)
        self._context = await playwright.chromium.launch_persistent_context(
            user_data_dir=str(self.config.profile_dir),
            headless=self.config.headless,
            args=["--no-first-run", "--no-default-browser-check"],
        )

    async def stop(self) -> None:
        """Close the persistent context if open."""
        if self._context is not None:
            await self._context.close()
            self._context = None

    def guard_conditional_access(self, page_text: str) -> None:
        """Raise the fail-closed blocker when Conditional Access demands enrolment."""
        if detect_conditional_access_block(page_text):
            raise BlockerConditionalAccess(
                "Conditional Access requires a managed/compliant device; "
                "enrolment and bypass are forbidden by policy"
            )
