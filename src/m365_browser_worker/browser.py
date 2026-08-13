"""Application-neutral Playwright persistent-browser boundary.

This module owns the browser/profile lifecycle primitives used by Microsoft 365
application adapters. It deliberately exposes no generic click/selector/script
surface and never exports authenticated session material.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from m365_browser_worker.auth_bootstrap import AuthOriginStatus, auth_origin_status
from m365_browser_worker.bootstrap_navigation import (
    AUTH_BOOTSTRAP_NAVIGATE_OPERATION,
    PLANNER_WEB_BOOTSTRAP_URL,
    evaluate_bootstrap_target,
    is_reusable_bootstrap_page,
)
from m365_browser_worker.egress import enforce_route_egress
from m365_mcp.config import browser_runtime_settings
from planner_mcp.errors import (
    BlockerConditionalAccess,
    PolicyDenied,
    UiContractUnattested,
    WorkerUnavailable,
)
from planner_mcp.ui_contract import common_auth_attested, load_status


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
    Individual semantic operations use fresh operation-scoped pages so page-local
    navigation/DOM state cannot bleed into the next operation.
    """

    def __init__(self, config: BrowserConfig | None = None) -> None:
        self.config = config or BrowserConfig.from_env()
        self._playwright: Any = None
        self._context: Any = None

    @property
    def started(self) -> bool:
        """Return whether this process currently owns a live Chromium context."""
        return self._context is not None and self._playwright is not None

    def is_dedicated_persistent_profile(self) -> bool:
        """Return whether this is the dedicated persistent professional profile.

        A throwaway or wrong profile directory is rejected so authentication
        bootstrap can only proceed against the sanctioned professional context.
        Mock mode is never the dedicated live profile.
        """
        if self.config.is_mock:
            return False
        expected_profile_dir, _headless, _mode = browser_runtime_settings()
        return self.started and self.config.profile_dir == expected_profile_dir

    def auth_origin_approved(self) -> bool:
        """Return whether the live context may begin/continue auth bootstrap.

        True only when no page is open yet (bootstrap may begin navigation) or
        every open page is on an approved Microsoft authentication origin. Raw
        URLs are reduced to a closed host allowlist decision and never returned.
        """
        if not self.started:
            return False
        status = auth_origin_status(tuple(page.url for page in self._context.pages))
        return status is not AuthOriginStatus.NON_APPROVED_ORIGIN

    def common_auth_attested(self) -> bool:
        """Return whether the ``common.auth`` UIContract fragment is attested.

        Fragment-scoped: delegates to ``planner_mcp.ui_contract.common_auth_attested``
        which inspects ONLY the ``common.auth`` fragment rather than the aggregated
        common+Planner attestation status. This lets LIVE auth report AUTHENTICATED
        once ``common.auth`` is legitimately attested even while Planner fragments
        remain UNVERIFIED. The stricter full-contract ``ensure_live_allowed`` gate
        is unchanged.
        """
        return common_auth_attested()

    def ensure_live_allowed(self, operation: str) -> None:
        """Fail closed for semantic live operations without an attested UIContract."""
        status = load_status()
        if not status.attested:
            raise UiContractUnattested(
                f"live browser operation '{operation}' blocked",
                ui_contract_version=status.version,
            )

    async def navigate_auth_bootstrap(self) -> None:
        """Navigate ONCE to the FIXED Planner Web bootstrap target.

        This is the only navigation primitive in the worker and it takes no
        arguments: the destination is the production constant
        ``PLANNER_WEB_BOOTSTRAP_URL``. The constant is re-evaluated through the
        closed egress policy on every call and navigation is refused unless that
        policy allows it, so the browser can never be steered elsewhere. The
        Playwright route interceptor stays installed, so redirects and
        sub-resources continue to be evaluated.

        An already-open page is reused only when it is a neutral placeholder;
        otherwise exactly ONE new page is opened in the same persistent context.
        There is no retry, no credential entry and no MFA automation, and no
        URL/DOM/page text/cookie/token is returned.
        """
        if not self.started:
            raise WorkerUnavailable(
                "authentication bootstrap navigation requires a started live browser",
                operation=AUTH_BOOTSTRAP_NAVIGATE_OPERATION,
            )

        decision = evaluate_bootstrap_target()
        if not decision.allowed:
            raise PolicyDenied(
                "authentication bootstrap navigation denied by closed egress policy",
                operation=AUTH_BOOTSTRAP_NAVIGATE_OPERATION,
                reason=decision.reason,
            )

        context = self._context
        page = None
        for candidate in context.pages:
            if is_reusable_bootstrap_page(str(candidate.url)):
                page = candidate
                break
        if page is None:
            page = await context.new_page()

        # Exactly one navigation per operator call; no retry loop.
        await page.goto(PLANNER_WEB_BOOTSTRAP_URL)

    @asynccontextmanager
    async def operation_page(self, operation: str) -> AsyncIterator[Any]:
        """Yield one fresh page and close it deterministically after the operation.

        Authentication/session state remains intentionally shared only through the
        process-owned persistent browser context. Page-local state is never reused.
        This primitive is internal infrastructure and does not expose navigation,
        selectors, scripts or browser state through the worker API.
        """
        if not self.started:
            raise WorkerUnavailable(
                "browser context is not available for an operation-scoped page",
                operation=operation,
            )

        context = self._context
        page = await context.new_page()
        try:
            yield page
        finally:
            await page.close()

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
