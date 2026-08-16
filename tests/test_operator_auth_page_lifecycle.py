"""Regression suite for AUTH-116: deterministic AUTH-* page lifecycle.

Root cause (the bug this suite pins): ``PersistentBrowser.navigate_auth_bootstrap``
only reused neutral placeholder pages (``about:blank`` / ``chrome://newtab``).
The dedicated persistent professional profile RESTORES its Planner Web tab on
launch, so the live context already holds ONE ``planner_web`` page when the
operator runs ``scripts/operator_auth_run.py``. Because that page was not
reusable, ``navigate`` opened a SECOND page. The two-page context then fails
``_require_single_auth_page`` (used by ``begin_email_stage`` /
``submit_operator_signin`` / ``observe``) with:

    operator sign-in requires exactly one open authentication page

The deterministic fix reuses the worker-OWNED ``planner_web`` page (a
process-owned persistent-profile tab) for navigation, collapsing the context back
to exactly one page. It never closes an arbitrary/external page and never
selects an identity. Ambiguous topologies (multiple planner_web / multiple
neutral pages) still fail closed.

These tests drive the REAL ``PersistentBrowser.navigate_auth_bootstrap`` with an
injected fake Playwright context (no Chromium, no credentials, no mutations).
"""

from __future__ import annotations

import tempfile
from pathlib import Path

from m365_browser_worker.bootstrap_navigation import (
    PLANNER_WEB_BOOTSTRAP_URL,
    is_planner_web_surface_url,
    is_reusable_bootstrap_page,
)
from m365_browser_worker.browser import BrowserConfig, PersistentBrowser
from planner_mcp.errors import PolicyDenied


class _FakePage:
    def __init__(self, url: str = "about:blank") -> None:
        self.url = url
        self.goto_calls: list[str] = []

    async def goto(self, url: str) -> None:
        self.goto_calls.append(url)
        self.url = url


class _FakeContext:
    def __init__(self, pages: list[_FakePage] | None = None) -> None:
        self.pages = pages if pages is not None else []
        self.new_page_calls = 0

    async def new_page(self) -> _FakePage:
        self.new_page_calls += 1
        page = _FakePage()
        self.pages.append(page)
        return page


def _browser_with_context(pages: list[_FakePage]) -> PersistentBrowser:
    """Build a ``started`` browser whose ``navigate`` uses an injected context.

    Bypasses ``__init__`` (which would read env/M365 config) and instead wires a
    fake but realistic state: a live Chromium context owned by this process with
    the supplied page set. ``navigate_auth_bootstrap`` only reads
    ``self.started`` (via ``self._context``/``self._playwright``) and the egress
    decision, so this is faithful to the production code path.
    """
    browser = PersistentBrowser.__new__(PersistentBrowser)
    browser.config = BrowserConfig(
        profile_dir=Path(tempfile.gettempdir()) / "operator-auth-lifecycle-fake-profile",
        headless=True,
        mode="live",
    )
    browser._playwright = object()  # truthy -> started returns True
    browser._context = _FakeContext(pages)
    browser._signin_surface_resolved = False
    return browser


def _open_auth_pages(context_pages: list[_FakePage]) -> list[_FakePage]:
    return [p for p in context_pages if str(p.url)]


# -------------------------------------------------------------------------
# The bug: a persistent profile that restores a Planner Web tab must NOT spawn
# a second page. The context must stay at exactly one open page so the later
# single-page guard succeeds.
# -------------------------------------------------------------------------


async def test_navigate_reuses_restored_planner_web_page_and_keeps_one_page() -> None:
    planner_page = _FakePage("https://planner.cloud.microsoft/")
    browser = _browser_with_context([planner_page])

    await browser.navigate_auth_bootstrap()

    # The SAME planner_web page was navigated; no second page was opened.
    assert planner_page.goto_calls == [PLANNER_WEB_BOOTSTRAP_URL]
    assert browser._context.new_page_calls == 0
    assert len(browser._context.pages) == 1
    # The single-page invariant consumed by begin_email_stage / operator-submit
    # / observe must now hold on the live context.
    assert len(_open_auth_pages(browser._context.pages)) == 1


async def test_navigate_reuses_restored_planner_deep_link_page() -> None:
    # The persistent profile may restore a premium-plan deep link rather than the
    # root; it is still a worker-owned planner_web surface and must be reused.
    deep_link = _FakePage(
        "https://planner.cloud.microsoft/webui/premiumplan/"
        "50191d3f-5092-44c7-b719-e0efd56532aa/org/"
        "c5837053-931c-4251-a5a4-81b512a225e9/view/grid"
    )
    browser = _browser_with_context([deep_link])

    await browser.navigate_auth_bootstrap()

    assert deep_link.goto_calls == [PLANNER_WEB_BOOTSTRAP_URL]
    assert browser._context.new_page_calls == 0
    assert len(browser._context.pages) == 1


# -------------------------------------------------------------------------
# Fail-closed: a neutral placeholder is still reused (no behaviour regression),
# and an arbitrary/external page is never hijacked or closed.
# -------------------------------------------------------------------------


async def test_navigate_still_reuses_neutral_placeholder() -> None:
    neutral = _FakePage("about:blank")
    browser = _browser_with_context([neutral])

    await browser.navigate_auth_bootstrap()

    assert neutral.goto_calls == [PLANNER_WEB_BOOTSTRAP_URL]
    assert browser._context.new_page_calls == 0
    assert len(browser._context.pages) == 1


async def test_navigate_never_closes_or_reuses_arbitrary_external_page() -> None:
    # An external, non-worker-owned, non-approved page: navigate must neither
    # close it nor navigate it. It opens its OWN page and leaves the external
    # page untouched (preserving fail-closed page ownership).
    external = _FakePage("https://example.com/dashboard")
    browser = _browser_with_context([external])

    await browser.navigate_auth_bootstrap()

    # External page is untouched.
    assert external.goto_calls == []
    # Worker opened exactly one new page for the bootstrap target.
    assert browser._context.new_page_calls == 1
    assert len(browser._context.pages) == 2
    new_page = [p for p in browser._context.pages if p is not external][0]
    assert new_page.goto_calls == [PLANNER_WEB_BOOTSTRAP_URL]


# -------------------------------------------------------------------------
# Ambiguous topologies still fail closed (no guessing which page to hijack).
# -------------------------------------------------------------------------


async def test_navigate_fails_closed_on_multiple_planner_web_pages() -> None:
    browser = _browser_with_context(
        [
            _FakePage("https://planner.cloud.microsoft/"),
            _FakePage("https://planner.cloud.microsoft/webui/plan/x"),
        ]
    )
    try:
        await browser.navigate_auth_bootstrap()
    except PolicyDenied:
        pass
    else:
        raise AssertionError("expected PolicyDenied on ambiguous planner_web topology")
    assert browser._context.new_page_calls == 0


async def test_navigate_fails_closed_on_multiple_neutral_pages() -> None:
    browser = _browser_with_context(
        [_FakePage("about:blank"), _FakePage("chrome://newtab")]
    )
    try:
        await browser.navigate_auth_bootstrap()
    except PolicyDenied:
        pass
    else:
        raise AssertionError("expected PolicyDenied on ambiguous neutral topology")
    assert browser._context.new_page_calls == 0


# -------------------------------------------------------------------------
# Boundary: zero pages opens exactly one; the planner_web host predicate and
# the neutral predicate keep their closed semantics.
# -------------------------------------------------------------------------


async def test_navigate_opens_one_page_when_context_empty() -> None:
    browser = _browser_with_context([])
    await browser.navigate_auth_bootstrap()
    assert browser._context.new_page_calls == 1
    assert len(browser._context.pages) == 1
    assert browser._context.pages[0].goto_calls == [PLANNER_WEB_BOOTSTRAP_URL]


def test_planner_web_surface_predicate_is_closed() -> None:
    assert is_planner_web_surface_url("https://planner.cloud.microsoft/") is True
    assert (
        is_planner_web_surface_url(
            "https://planner.cloud.microsoft/webui/premiumplan/x"
        )
        is True
    )
    assert is_planner_web_surface_url("https://login.microsoftonline.com/") is False
    assert is_planner_web_surface_url("https://example.com/") is False
    assert is_planner_web_surface_url("about:blank") is False


def test_reusable_page_predicate_is_unchanged() -> None:
    assert is_reusable_bootstrap_page("about:blank") is True
    assert is_reusable_bootstrap_page("chrome://newtab") is True
    assert is_reusable_bootstrap_page("https://planner.cloud.microsoft/") is False
