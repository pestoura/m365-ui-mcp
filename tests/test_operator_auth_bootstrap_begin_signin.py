"""Security regression suite for the OPERATOR-ONLY begin-signin transition.

Second step of the two-step operator flow (navigation to Planner Web, then
begin-signin to the fixed Microsoft auth target). Covers, explicitly:

* the fixed target is exactly login.microsoftonline.com (no URL/parameter input);
* loopback socket peer accepted; Docker-network / non-loopback peer denied;
* X-Forwarded-For / X-Real-IP / Forwarded cannot spoof loopback;
* any query string and any non-empty body are rejected;
* the target requires BOTH existing browser egress ALLOW on the fixed Microsoft
  auth target AND an existing approved auth origin; Graph / non-HTTPS / arbitrary
  targets are impossible/denied;
* the source classifier permits only planner_web / neutral / approved-auth
  sources; arbitrary sources are denied;
* approved-auth source is idempotent (permitted across calls);
* exactly ONE navigation happens per call;
* the existing /auth/status guard and AuthBootstrapGuard are unchanged;
* the endpoint is absent from the MCP tool registry / capability projection /
  agent card / typed /operations dispatcher and the control-plane worker client
  has no proxy path to it;
* the operator wrapper accepts no arguments and contains no URL parameterization.
"""

from __future__ import annotations

import asyncio
import os
import subprocess
from collections.abc import Iterator
from pathlib import Path

import httpx
import pytest

from m365_browser_worker.bootstrap_navigation import (
    AUTH_BEGIN_SIGNIN_OPERATION,
    MICROSOFT_AUTH_BOOTSTRAP_URL,
    MICROSOFT_AUTH_TARGET_CLASS,
    SourceClassStatus,
    classify_begin_signin_source,
    evaluate_microsoft_auth_target,
    is_loopback_peer,
    is_planner_web_surface_url,
)
from m365_browser_worker.browser import BrowserConfig, PersistentBrowser
from m365_browser_worker.egress import evaluate_browser_egress
from m365_mcp.config import browser_runtime_settings
from m365_mcp.tool_registry import default_tool_registry
from planner_browser_worker.app import create_app
from planner_mcp.errors import PolicyDenied, UiContractUnattested, WorkerUnavailable
from planner_mcp.worker_client import WorkerClient

ROOT = Path(__file__).resolve().parent.parent
# Never created or written: the tests inject a duck-typed context.
_UNUSED_PROFILE_DIR = Path(__file__).resolve().parent / "data" / "unused-live-profile"
BEGIN_SIGNIN_PATH = "/auth/bootstrap/begin-signin"


# --------------------------------------------------------------------------
# Test doubles
# --------------------------------------------------------------------------


class _FakeLocator:
    """Minimal Playwright locator double.

    Models a role-based locator so planner_web tests can express
    ``page.get_by_role('button', name='Sign In', exact=True)``, then
    ``count()`` and ``click()``. The fake page owns the candidate set produced
    by ``get_by_role`` — the wire-up between page state and role candidates is
    the production responsibility under test (RED: production never resolves or
    clicks a Sign In candidate).
    """

    def __init__(self, page: _FakePage, role: str, name: str, exact: bool) -> None:
        self._page = page
        self._role = role
        self._name = name
        self._exact = exact
        self.clicks = 0

    async def count(self) -> int:
        # Delegate to the page so the production code (not the test) decides
        # which elements match the role/name/exact selector. In RED, production
        # never queries the page, so this returns the authored candidate set.
        return self._page._sign_in_candidates(self._role, self._name, self._exact)

    async def click(self) -> None:
        # 1:1 with the real locator contract — click must be fail-closed on
        # count != 1.
        assert await self.count() == 1, "click() requires exactly one matching element"
        self.clicks += 1
        self._page._record_sign_in_click()


class _FakePage:
    def __init__(self, url: str = "about:blank", landing_url: str | None = None) -> None:
        self.url = url
        # When set, ``goto`` leaves the page on ``landing_url`` instead of the
        # target — used to simulate a navigation that does not commit (the
        # AUTH-113 about:blank / stale-page defect). None means a normal
        # successful navigation to the target.
        self.landing_url = landing_url
        self.goto_calls: list[str] = []
        # Sign In candidate modeling for planner_web click tests.
        self.sign_in_candidates: int = 1
        self.sign_in_clicks: int = 0
        self.credential_fills: list[str] = []
        self.credential_types: list[str] = []
        self.credential_presses: list[str] = []
        self.popup_urls_on_click: list[str] = []
        # Popups appended to context.pages ONLY after the Sign In click
        # coroutine has returned and the caller has snapshotted context.pages —
        # models a popup window that opens asynchronously after the click
        # resolves (delayed-popup regression).
        self.delayed_popup_urls_after_click: list[str] = []
        self.delayed_popup_delay_s: float = 0.02
        self._context = None
        self.closed = False

    async def goto(self, url: str) -> None:
        self.goto_calls.append(url)
        self.url = self.landing_url if self.landing_url is not None else url

    def get_by_role(self, role: str, *, name: str, exact: bool = False) -> _FakeLocator:
        # Exposes the role-based locator API used by the planner_web Sign In
        # click path. The candidate count is owned by the page state so the
        # production resolver (RED: absent) is what would populate it.
        return _FakeLocator(self, role, name, exact)

    def _sign_in_candidates(self, role: str, name: str, exact: bool) -> int:
        # The test-authored candidate count. Production is responsible for
        # deriving this from the live DOM; the fake only mirrors it.
        return self.sign_in_candidates

    def _record_sign_in_click(self) -> None:
        self.sign_in_clicks += 1
        if self.popup_urls_on_click:
            assert self._context is not None
            for popup_url in self.popup_urls_on_click:
                popup = _FakePage(popup_url)
                popup._context = self._context
                self._context.pages.append(popup)
            return
        if self.delayed_popup_urls_after_click:
            # Append the fake popups ONLY after the Sign In click coroutine
            # returns and the caller has snapshotted context.pages, modeling a
            # window that opens asynchronously after the click resolves.
            assert self._context is not None
            loop = asyncio.get_running_loop()
            delay = self.delayed_popup_delay_s
            urls = self.delayed_popup_urls_after_click
            ctx = self._context

            async def _append_late_popups() -> None:
                await asyncio.sleep(delay)
                for popup_url in urls:
                    popup = _FakePage(popup_url)
                    popup._context = ctx
                    ctx.pages.append(popup)

            loop.create_task(_append_late_popups())
            return
        self.url = (
            self.landing_url
            if self.landing_url is not None
            else MICROSOFT_AUTH_BOOTSTRAP_URL
        )

    async def close(self) -> None:
        self.closed = True
        if self._context is not None and self in self._context.pages:
            self._context.pages.remove(self)

    async def fill(self, selector: str, value: str) -> None:
        # Credential primitive — must never be exercised by begin-signin.
        self.credential_fills.append(value)

    async def type(self, text: str) -> None:
        self.credential_types.append(text)

    async def press(self, key: str) -> None:
        self.credential_presses.append(key)


class _FakeContext:
    def __init__(self, pages: list[_FakePage] | None = None) -> None:
        self.pages = pages if pages is not None else []
        for page in self.pages:
            page._context = self
        self.new_page_calls = 0

    async def new_page(self) -> _FakePage:
        self.new_page_calls += 1
        page = _FakePage()
        page._context = self
        self.pages.append(page)
        return page


class _BeginSigninBrowser:
    """Duck-typed PersistentBrowser exposing the begin-signin surface."""

    def __init__(
        self,
        *,
        started: bool = True,
        dedicated: bool = True,
        source_permitted: bool = True,
        full_attested: bool = False,
        auth_attested: bool = False,
        pages: list[_FakePage] | None = None,
    ) -> None:
        self._started = started
        self._dedicated = dedicated
        self._source_permitted = source_permitted
        self._full_attested = full_attested
        self._auth_attested = auth_attested
        self.context = _FakeContext(pages)
        self.begin_calls = 0
        self.egress_evaluations = 0
        self.deny_egress = False

    @property
    def started(self) -> bool:
        return self._started

    def is_dedicated_persistent_profile(self) -> bool:
        return self._dedicated

    def begin_signin_source_permitted(self) -> bool:
        return self._source_permitted

    def auth_origin_approved(self) -> bool:
        # AuthBootstrapGuard wiring in create_app uses this; for begin-signin
        # tests it mirrors source permission (callee is separate from the
        # dedicated begin-signin guard).
        return self._source_permitted

    def common_auth_attested(self) -> bool:
        return self._auth_attested

    def full_attested(self) -> bool:
        return self._full_attested

    def ensure_live_allowed(self, operation: str) -> None:
        if not self._full_attested:
            raise UiContractUnattested(f"blocked {operation}")

    async def begin_auth_signin(self) -> None:
        # Mirrors production ordering: state, source, then egress, then one goto.
        if not self._started:
            raise WorkerUnavailable("no browser", operation=AUTH_BEGIN_SIGNIN_OPERATION)
        if not self._dedicated:
            raise PolicyDenied(
                "not dedicated", operation=AUTH_BEGIN_SIGNIN_OPERATION
            )
        if not self._source_permitted:
            raise PolicyDenied(
                "source not permitted", operation=AUTH_BEGIN_SIGNIN_OPERATION
            )
        self.egress_evaluations += 1
        decision = evaluate_microsoft_auth_target()
        if self.deny_egress or not decision.allowed:
            raise PolicyDenied(
                "denied by egress policy",
                operation=AUTH_BEGIN_SIGNIN_OPERATION,
            )
        self.begin_calls += 1
        page = None
        for candidate in self.context.pages:
            from m365_browser_worker.bootstrap_navigation import (
                is_reusable_bootstrap_page,
            )

            if is_reusable_bootstrap_page(str(candidate.url)):
                page = candidate
                break
        if page is None:
            page = await self.context.new_page()
        await page.goto(MICROSOFT_AUTH_BOOTSTRAP_URL)


@pytest.fixture()
def live_env() -> Iterator[None]:
    previous = {
        "PLANNER_MODE": os.environ.get("PLANNER_MODE"),
        "M365_MODE": os.environ.get("M365_MODE"),
    }
    os.environ["PLANNER_MODE"] = "live"
    os.environ["M365_MODE"] = "live"
    try:
        yield
    finally:
        for name in ("PLANNER_MODE", "M365_MODE"):
            if previous[name] is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = previous[name]


def _client(app, *, peer: tuple[str, int] = ("127.0.0.1", 4242)) -> httpx.AsyncClient:
    transport = httpx.ASGITransport(app=app, client=peer)
    return httpx.AsyncClient(transport=transport, base_url="http://worker")


# --------------------------------------------------------------------------
# Fixed target / no parameters / egress + auth-origin requirement
# --------------------------------------------------------------------------


def test_microsoft_auth_target_is_the_fixed_constant() -> None:
    assert MICROSOFT_AUTH_BOOTSTRAP_URL == "https://login.microsoftonline.com/"
    assert MICROSOFT_AUTH_TARGET_CLASS == "microsoft_auth"


def test_fixed_target_is_allowed_by_egress_policy() -> None:
    decision = evaluate_microsoft_auth_target()
    assert decision.allowed is True
    assert decision == evaluate_browser_egress(MICROSOFT_AUTH_BOOTSTRAP_URL)


def test_begin_auth_signin_helper_takes_no_target_argument() -> None:
    import inspect

    signature = inspect.signature(PersistentBrowser.begin_auth_signin)
    assert list(signature.parameters) == ["self"]


def test_graph_and_non_https_targets_remain_denied() -> None:
    for url in (
        "https://example.com/",
        "https://evil.example.com/login",
        "https://graph.microsoft.com/v1.0/me",
        "https://graph.example.microsoft.com/",
        "http://login.microsoftonline.com/",
        "https://login.microsoftonline.com.evil.example/",
    ):
        assert evaluate_browser_egress(url).allowed is False


def test_target_evaluator_returns_existing_egress_decision() -> None:
    decision = evaluate_microsoft_auth_target()
    assert decision.reason == "MICROSOFT_M365_ALLOWLIST"


# --------------------------------------------------------------------------
# Source classifier (permitted begin-signin sources only)
# --------------------------------------------------------------------------


def test_source_classifier_allows_planner_web_host() -> None:
    assert (
        classify_begin_signin_source(
            ("https://planner.cloud.microsoft/",)
        )
        == SourceClassStatus.PLANNER_WEB
    )
    assert (
        classify_begin_signin_source(
            ("https://sub.planner.cloud.microsoft/board",)
        )
        == SourceClassStatus.PLANNER_WEB
    )


def test_source_classifier_allows_neutral_pages() -> None:
    assert (
        classify_begin_signin_source(
            ("about:blank", "chrome://newtab")
        )
        == SourceClassStatus.NEUTRAL
    )


def test_source_classifier_allows_approved_auth_origin() -> None:
    assert (
        classify_begin_signin_source(
            ("https://login.microsoftonline.com/kmsi",)
        )
        == SourceClassStatus.APPROVED_AUTH
    )
    # Idempotent: an approved-auth source stays approved on a second call.
    assert (
        classify_begin_signin_source(
            ("https://login.microsoftonline.com/kmsi",)
        )
        == SourceClassStatus.APPROVED_AUTH
    )


def test_source_classifier_denies_arbitrary_origin() -> None:
    assert (
        classify_begin_signin_source(
            ("https://example.com/",)
        )
        == SourceClassStatus.NON_APPROVED
    )


def test_source_classifier_denies_mixed_sources() -> None:
    # A permitted source mixed with an arbitrary one fails closed.
    assert (
        classify_begin_signin_source(
            ("https://planner.cloud.microsoft/", "https://example.com/")
        )
        == SourceClassStatus.NON_APPROVED
    )


def test_source_classifier_empty_means_planner_web_allowed() -> None:
    # No page opened yet: begin-signin may proceed from a fresh page.
    assert classify_begin_signin_source(()) == SourceClassStatus.PLANNER_WEB


# --------------------------------------------------------------------------
# Loopback admission (socket level only)
# --------------------------------------------------------------------------


def test_is_loopback_peer_socket_level_only() -> None:
    assert is_loopback_peer("127.0.0.1") is True
    assert is_loopback_peer("::1") is True
    assert is_loopback_peer("::ffff:127.0.0.1") is True
    wildcard = ".".join(["0", "0", "0", "0"])
    for peer in ("172.18.0.5", "10.0.0.7", "192.168.1.10", wildcard, "", None):
        assert is_loopback_peer(peer) is False


async def test_loopback_peer_accepted(live_env) -> None:
    browser = _BeginSigninBrowser()
    app = create_app(browser=browser)
    async with _client(app) as client:
        response = await client.post(BEGIN_SIGNIN_PATH)
    assert response.status_code == 200
    assert response.json() == {
        "ok": True,
        "target_class": "microsoft_auth",
        "auth_state": "UNKNOWN",
    }
    assert browser.begin_calls == 1


async def test_docker_network_peer_denied(live_env) -> None:
    browser = _BeginSigninBrowser()
    app = create_app(browser=browser)
    async with _client(app, peer=("172.18.0.5", 5555)) as client:
        response = await client.post(BEGIN_SIGNIN_PATH)
    assert response.status_code == 404
    assert browser.begin_calls == 0
    assert browser.egress_evaluations == 0


async def test_forwarded_headers_cannot_spoof_loopback(live_env) -> None:
    browser = _BeginSigninBrowser()
    app = create_app(browser=browser)
    spoofs = (
        {"X-Forwarded-For": "127.0.0.1"},
        {"X-Forwarded-For": "127.0.0.1, 172.18.0.5"},
        {"X-Real-IP": "127.0.0.1"},
        {"Forwarded": 'for="127.0.0.1"'},
        {"X-Forwarded-For": "::1"},
    )
    async with _client(app, peer=("172.18.0.9", 6666)) as client:
        for headers in spoofs:
            response = await client.post(BEGIN_SIGNIN_PATH, headers=headers)
            assert response.status_code == 404
    assert browser.begin_calls == 0


# --------------------------------------------------------------------------
# No parameters: query and body rejected
# --------------------------------------------------------------------------


async def test_query_string_rejected(live_env) -> None:
    browser = _BeginSigninBrowser()
    app = create_app(browser=browser)
    async with _client(app) as client:
        for query in ("?url=https://example.com", "?x=1", "?target=auth"):
            response = await client.post(f"{BEGIN_SIGNIN_PATH}{query}")
            assert response.status_code == 400
            assert response.json()["detail"]["error"] == "INVALID_REQUEST"
    assert browser.begin_calls == 0


async def test_non_empty_body_rejected(live_env) -> None:
    browser = _BeginSigninBrowser()
    app = create_app(browser=browser)
    async with _client(app) as client:
        response = await client.post(BEGIN_SIGNIN_PATH, json={"url": "https://x"})
        assert response.status_code == 400
        response = await client.post(BEGIN_SIGNIN_PATH, content=b"https://x")
        assert response.status_code == 400
    assert browser.begin_calls == 0


# --------------------------------------------------------------------------
# Guard fail-closed: egress allow + auth-origin approval both required
# --------------------------------------------------------------------------


async def test_browser_not_started_fails_closed(live_env) -> None:
    browser = _BeginSigninBrowser(started=False)
    app = create_app(browser=browser)
    async with _client(app) as client:
        response = await client.post(BEGIN_SIGNIN_PATH)
    assert response.status_code == 503
    assert browser.begin_calls == 0


async def test_wrong_profile_fails_closed(live_env) -> None:
    browser = _BeginSigninBrowser(dedicated=False)
    app = create_app(browser=browser)
    async with _client(app) as client:
        response = await client.post(BEGIN_SIGNIN_PATH)
    assert response.status_code == 503
    assert browser.begin_calls == 0


async def test_arbitrary_source_fails_closed(live_env) -> None:
    # Source permitted MUST be True; an arbitrary origin source fails closed.
    browser = _BeginSigninBrowser(source_permitted=False)
    app = create_app(browser=browser)
    async with _client(app) as client:
        response = await client.post(BEGIN_SIGNIN_PATH)
    assert response.status_code == 503
    assert browser.begin_calls == 0


async def test_egress_policy_invoked_and_denial_fails_closed(live_env) -> None:
    browser = _BeginSigninBrowser()
    browser.deny_egress = True
    app = create_app(browser=browser)
    async with _client(app) as client:
        response = await client.post(BEGIN_SIGNIN_PATH)
    assert response.status_code == 503
    assert browser.egress_evaluations == 1
    assert browser.begin_calls == 0


async def test_exactly_one_navigation_per_call(live_env) -> None:
    page = _FakePage("about:blank")
    browser = _BeginSigninBrowser(pages=[page])
    app = create_app(browser=browser)
    async with _client(app) as client:
        assert (await client.post(BEGIN_SIGNIN_PATH)).status_code == 200
    assert browser.begin_calls == 1
    assert page.goto_calls == [MICROSOFT_AUTH_BOOTSTRAP_URL]
    assert browser.context.new_page_calls == 0
    async with _client(app) as client:
        assert (await client.post(BEGIN_SIGNIN_PATH)).status_code == 200
    assert browser.begin_calls == 2
    assert browser.context.new_page_calls == 1
    assert browser.context.pages[1].goto_calls == [MICROSOFT_AUTH_BOOTSTRAP_URL]


def test_real_browser_begin_auth_signin_requires_started_context() -> None:
    browser = PersistentBrowser(
        BrowserConfig(profile_dir=_UNUSED_PROFILE_DIR, mode="live")
    )
    with pytest.raises(WorkerUnavailable):
        import asyncio

        asyncio.run(browser.begin_auth_signin())


def test_real_browser_begin_auth_signin_exact_target() -> None:
    from m365_mcp.config import browser_runtime_settings

    expected_profile_dir, _headless, _mode = browser_runtime_settings()
    browser = PersistentBrowser(BrowserConfig(profile_dir=expected_profile_dir, mode="live"))
    context = _FakeContext([_FakePage("about:blank")])
    browser._context = context  # noqa: SLF001 - injecting a duck-typed context
    browser._playwright = object()  # noqa: SLF001
    import asyncio

    asyncio.run(browser.begin_auth_signin())
    assert context.pages[0].goto_calls == [MICROSOFT_AUTH_BOOTSTRAP_URL]
    assert context.new_page_calls == 0


def test_response_leaks_no_url_or_secret_material(live_env) -> None:
    browser = _BeginSigninBrowser()
    app = create_app(browser=browser)
    import asyncio

    async def _run() -> str:
        async with _client(app) as client:
            response = await client.post(BEGIN_SIGNIN_PATH)
        return response.text.lower()

    body = asyncio.run(_run())
    for forbidden in (
        "login.microsoftonline.com",
        "http",
        "cookie",
        "token",
        "password",
        "storage_state",
        "upn",
        "tenant",
        "bearer",
        "<html",
    ):
        assert forbidden not in body


async def test_existing_auth_status_guard_unchanged(live_env) -> None:
    # The existing /auth/status guard must remain intact: dedicated professional
    # profile + approved origin. Begin-signin must not relax it.
    browser = _BeginSigninBrowser()
    app = create_app(browser=browser)
    async with _client(app) as client:
        assert (await client.get("/auth/status")).status_code in (200, 503)


# --------------------------------------------------------------------------
# Absent from every public catalog / no control-plane proxy
# --------------------------------------------------------------------------


def test_endpoint_absent_from_mcp_tool_catalog() -> None:
    names = set(default_tool_registry().names())
    for name in names:
        assert "begin" not in name
        assert "signin" not in name
        assert "bootstrap" not in name
    assert "auth_begin_signin" not in names
    assert "planner_auth_begin_signin" not in names


def test_worker_client_has_no_begin_signin_proxy() -> None:
    attributes = dir(WorkerClient)
    assert not [
        attribute
        for attribute in attributes
        if "begin" in attribute or "signin" in attribute
    ]
    source = (ROOT / "src" / "planner_mcp" / "worker_client.py").read_text(encoding="utf-8")
    assert BEGIN_SIGNIN_PATH not in source


def test_no_typed_worker_operation_reaches_begin_signin() -> None:
    from m365_browser_worker.protocol import WorkerOperation

    for operation in WorkerOperation:
        assert "begin" not in operation.value
        assert "signin" not in operation.value
    source = (ROOT / "src" / "planner_browser_worker" / "app.py").read_text(encoding="utf-8")
    dispatcher = source.split("async def dispatch_semantic_operation", 1)[1]
    dispatcher = dispatcher.split('@app.post("/operations"', 1)[0]
    assert "begin_signin" not in dispatcher


def test_control_plane_registration_does_not_expose_begin_signin() -> None:
    for relative in (
        "src/planner_mcp/registration.py",
        "src/planner_mcp/tools.py",
        "src/m365_mcp/apps/planner/public_surface.py",
    ):
        text = (ROOT / relative).read_text(encoding="utf-8")
        assert "begin_signin" not in text
        assert BEGIN_SIGNIN_PATH not in text


def test_operation_only_in_begin_signin_operation_constant() -> None:
    assert AUTH_BEGIN_SIGNIN_OPERATION == "auth_begin_signin"
    source = (
        ROOT / "src" / "m365_browser_worker" / "bootstrap_navigation.py"
    ).read_text(encoding="utf-8")
    # The fixed Microsoft auth constant must not be configurable via env.
    assert 'MICROSOFT_AUTH_BOOTSTRAP_URL = "https://login.microsoftonline.com/"' in source
    assert "os.getenv" not in source


# --------------------------------------------------------------------------
# Operator wrapper
# --------------------------------------------------------------------------


def test_operator_wrapper_shape() -> None:
    script = ROOT / "scripts" / "operator_auth_bootstrap_begin_signin.sh"
    assert script.is_file()
    assert os.access(script, os.X_OK)
    text = script.read_text(encoding="utf-8")
    assert "docker exec" in text
    assert "planner-mcp-browser-worker-1" in text
    assert "127.0.0.1:8090/auth/bootstrap/begin-signin" in text
    # No URL/host/path argument may be accepted from the operator.
    assert '"$1"' not in text
    assert "$*" not in text
    assert 'if [ "$#" -ne 0 ]' in text
    # No URL parameterization: the constant must be hard-coded in the endpoint.
    assert "login.microsoftonline.com" not in text


def test_operator_wrapper_rejects_any_argument() -> None:
    script = ROOT / "scripts" / "operator_auth_bootstrap_begin_signin.sh"
    result = subprocess.run(  # noqa: S603
        ["/bin/bash", str(script), "https://example.com"],  # noqa: S607
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 2
    assert "no arguments" in result.stderr.lower()


def test_runbook_documents_begin_signin_invocation() -> None:
    text = (ROOT / "docs" / "authentication-and-mfa.md").read_text(encoding="utf-8")
    assert "AUTH-096" in text
    assert "scripts/operator_auth_bootstrap_begin_signin.sh" in text
    assert "docker exec planner-mcp-browser-worker-1" in text
    assert "127.0.0.1:8090/auth/bootstrap/begin-signin" in text


# --------------------------------------------------------------------------
# Topology fix: reuse the existing planner_web page (no second page, no duplicate)
# --------------------------------------------------------------------------


def _started_production_browser() -> PersistentBrowser:
    """Build a production PersistentBrowser with an injected fake context.

    Uses the dedicated runtime profile directory so that
    ``is_dedicated_persistent_profile()`` returns True as it would in the live
    operator flow.
    """
    profile_dir, _headless, _mode = browser_runtime_settings()
    browser = PersistentBrowser(BrowserConfig(profile_dir=profile_dir, mode="live"))
    browser._playwright = object()  # noqa: SLF001 - duck-typed context only
    return browser


def test_existing_planner_web_page_is_reused_for_begin_signin() -> None:
    # Single planner_web page open: begin-signin must reuse THAT page and must
    # not open a second page (no duplicate companion Planner page).
    context = _FakeContext([_FakePage("https://planner.cloud.microsoft/")])
    browser = _started_production_browser()
    browser._context = context  # noqa: SLF001
    asyncio.run(browser.begin_auth_signin())
    # Exactly one fixed Sign In click on the SAME existing page; no direct goto.
    assert context.pages[0].sign_in_clicks == 1
    assert context.pages[0].goto_calls == []
    assert context.new_page_calls == 0
    assert len(context.pages) == 1


def test_after_begin_signin_exactly_one_page_on_approved_auth_origin() -> None:
    context = _FakeContext([_FakePage("https://planner.cloud.microsoft/")])
    browser = _started_production_browser()
    browser._context = context  # noqa: SLF001
    asyncio.run(browser.begin_auth_signin())
    # After begin-signin: exactly one page, and it is on the approved Microsoft
    # auth origin (not a duplicate Planner page remaining alongside it).
    assert len(context.pages) == 1
    assert context.pages[0].url == MICROSOFT_AUTH_BOOTSTRAP_URL
    assert is_planner_web_surface_url(context.pages[0].url) is False


def test_no_duplicate_companion_planner_page_remains() -> None:
    context = _FakeContext([_FakePage("https://planner.cloud.microsoft/board")])
    browser = _started_production_browser()
    browser._context = context  # noqa: SLF001
    asyncio.run(browser.begin_auth_signin())
    planner_pages = [p for p in context.pages if is_planner_web_surface_url(p.url)]
    assert planner_pages == []  # the only page moved to auth origin, none left
    assert len(context.pages) == 1


def test_multiple_planner_web_pages_fail_closed() -> None:
    context = _FakeContext(
        [
            _FakePage("https://planner.cloud.microsoft/"),
            _FakePage("https://sub.planner.cloud.microsoft/board"),
        ]
    )
    browser = _started_production_browser()
    browser._context = context  # noqa: SLF001
    with pytest.raises(PolicyDenied):
        asyncio.run(browser.begin_auth_signin())
    # No navigation happened and no new page was opened on an ambiguous topology.
    assert context.new_page_calls == 0
    assert all(p.goto_calls == [] for p in context.pages)
    assert len(context.pages) == 2


def test_arbitrary_origin_source_fails_closed_without_hijacking() -> None:
    # Source classifier denies an arbitrary origin before any page selection.
    context = _FakeContext([_FakePage("https://example.com/")])
    browser = _started_production_browser()
    browser._context = context  # noqa: SLF001
    with pytest.raises(PolicyDenied):
        asyncio.run(browser.begin_auth_signin())
    assert context.new_page_calls == 0
    assert all(p.goto_calls == [] for p in context.pages)


def test_begin_signin_clicks_fixed_sign_in_on_planner_web_no_credentials() -> None:
    # RED: the planner_web branch must resolve the fixed Sign In button by
    # role and click exactly one candidate — it must NOT navigate via
    # page.goto on planner_web, and it must never exercise credential
    # primitives (fill / type / press / to_submit).
    import inspect

    source = inspect.getsource(PersistentBrowser.begin_auth_signin)
    # Credential entry is always forbidden.
    for forbidden in ("fill(", "type(", "press(", "to_submit"):
        assert forbidden not in source
    # The fixed Sign In locator must be resolved by role, then clicked exactly
    # once (gated on count() == 1).
    assert 'get_by_role("button", name="Sign In", exact=True)' in source
    assert ".click()" in source



def test_begin_signin_promotes_single_approved_popup_and_closes_planner_source() -> None:
    source = _planner_web_page_with_candidates(1)
    source.popup_urls_on_click = ["https://login.microsoftonline.com/common/oauth2/v2.0/authorize"]
    context = _FakeContext([source])
    browser = _started_production_browser()
    browser._context = context  # noqa: SLF001
    asyncio.run(browser.begin_auth_signin())
    assert source.closed is True
    assert len(context.pages) == 1
    popup = context.pages[0]
    assert popup is not source
    assert popup.closed is False
    assert popup.url.startswith("https://login.microsoftonline.com/")


def test_begin_signin_rejects_unapproved_popup_and_closes_only_new_popup() -> None:
    source = _planner_web_page_with_candidates(1)
    source.popup_urls_on_click = ["https://evil.example/"]
    context = _FakeContext([source])
    browser = _started_production_browser()
    browser._context = context  # noqa: SLF001
    with pytest.raises(PolicyDenied):
        asyncio.run(browser.begin_auth_signin())
    assert source.closed is False
    assert context.pages == [source]


def test_begin_signin_rejects_multiple_new_popups_and_closes_only_new_pages() -> None:
    source = _planner_web_page_with_candidates(1)
    source.popup_urls_on_click = [
        "https://login.microsoftonline.com/a",
        "https://login.microsoftonline.com/b",
    ]
    context = _FakeContext([source])
    browser = _started_production_browser()
    browser._context = context  # noqa: SLF001
    with pytest.raises(PolicyDenied):
        asyncio.run(browser.begin_auth_signin())
    assert source.closed is False
    assert context.pages == [source]


def test_begin_signin_promotes_delayed_approved_popup_after_click_returns() -> None:
    # Delayed-popup regression. The Planner Sign In click resolves immediately
    # (source Planner page remains Planner), then exactly ONE new fake popup is
    # appended to context.pages asynchronously AFTER the click returns (0.02s).
    # Desired production behavior: begin_auth_signin waits BOUNDEDLY for the
    # late popup, promotes it because its URL is an approved Microsoft auth
    # origin, closes ONLY the Planner source, leaves exactly one page (popup),
    # and returns success. Current production snapshots context.pages
    # synchronously after click() and sees no popup, so it treats the flow as
    # same-tab and fails the landing gate (RED).
    source = _planner_web_page_with_candidates(1)
    source.delayed_popup_urls_after_click = [
        "https://login.microsoftonline.com/common/oauth2/v2.0/authorize"
    ]
    context = _FakeContext([source])
    browser = _started_production_browser()
    browser._context = context  # noqa: SLF001
    asyncio.run(browser.begin_auth_signin())
    # Exactly the Planner source is closed; the late approved popup remains as
    # the single page.
    assert source.closed is True
    assert len(context.pages) == 1
    popup = context.pages[0]
    assert popup is not source
    assert popup.closed is False
    assert popup.url.startswith("https://login.microsoftonline.com/")


def test_begin_signin_rejects_multiple_delayed_popups() -> None:
    # Fail-closed: two new fake popups appear asynchronously AFTER the Sign In
    # click returns. Desired behavior closes ONLY the two new popups and
    # preserves the source Planner page (no promotion, no hijack). Current
    # production snapshots context.pages synchronously after click() and sees no
    # new pages, falling through to the same-tab path; it never observes the
    # delayed multi-popup topology (RED due missing popup-creation wait). We
    # keep the event loop alive after the call so the delayed popups actually
    # materialize, which current production leaves unhandled.
    source = _planner_web_page_with_candidates(1)
    source.delayed_popup_urls_after_click = [
        "https://login.microsoftonline.com/a",
        "https://login.microsoftonline.com/b",
    ]
    context = _FakeContext([source])
    browser = _started_production_browser()
    browser._context = context  # noqa: SLF001

    async def _run() -> None:
        with pytest.raises(PolicyDenied):
            await browser.begin_auth_signin()
        # Allow the asynchronously-scheduled delayed popups to materialize.
        await asyncio.sleep(0.05)

    asyncio.run(_run())
    # Source preserved; only the newly-spawned popups are closed.
    assert source.closed is False
    assert context.pages == [source]
# --------------------------------------------------------------------------
# Sign In resolution on planner_web (RED: production still always page.goto and
# does not resolve/click a Sign In candidate).
# --------------------------------------------------------------------------


def _planner_web_page_with_candidates(n: int) -> _FakePage:
    page = _FakePage("https://planner.cloud.microsoft/")
    page.sign_in_candidates = n
    return page


def test_planner_web_single_sign_in_candidate_clicks_once_no_goto() -> None:
    # Exactly one Sign In candidate on planner_web: begin-signin must click it
    # exactly once and must NOT page.goto the auth target.
    context = _FakeContext([_planner_web_page_with_candidates(1)])
    browser = _started_production_browser()
    browser._context = context  # noqa: SLF001
    asyncio.run(browser.begin_auth_signin())
    assert context.pages[0].sign_in_clicks == 1
    assert context.pages[0].goto_calls == []
    assert context.new_page_calls == 0


def test_planner_web_zero_sign_in_candidates_fails_closed() -> None:
    # No Sign In candidate: fail closed — no click, no navigation, no new page.
    context = _FakeContext([_planner_web_page_with_candidates(0)])
    browser = _started_production_browser()
    browser._context = context  # noqa: SLF001
    with pytest.raises(PolicyDenied):
        asyncio.run(browser.begin_auth_signin())
    assert context.pages[0].sign_in_clicks == 0
    assert context.pages[0].goto_calls == []
    assert context.new_page_calls == 0


def test_planner_web_multiple_sign_in_candidates_fails_closed() -> None:
    # Ambiguous topology: more than one Sign In candidate must fail closed.
    context = _FakeContext([_planner_web_page_with_candidates(2)])
    browser = _started_production_browser()
    browser._context = context  # noqa: SLF001
    with pytest.raises(PolicyDenied):
        asyncio.run(browser.begin_auth_signin())
    assert context.pages[0].sign_in_clicks == 0
    assert context.pages[0].goto_calls == []
    assert context.new_page_calls == 0


def test_post_click_landing_on_non_approved_origin_fails_closed() -> None:
    # After clicking Sign In, the post-click landing verification must still
    # fail closed if the committed origin is not an approved auth origin.
    page = _planner_web_page_with_candidates(1)
    page.landing_url = "https://example.com/blocked"
    context = _FakeContext([page])
    browser = _started_production_browser()
    browser._context = context  # noqa: SLF001
    with pytest.raises(PolicyDenied):
        asyncio.run(browser.begin_auth_signin())
    assert context.new_page_calls == 0


def test_neutral_page_still_uses_fixed_goto_and_no_click() -> None:
    # Neutral surface keeps the existing closed-target navigation and must not
    # click any Sign In candidate.
    context = _FakeContext([_FakePage("about:blank")])
    browser = _started_production_browser()
    browser._context = context  # noqa: SLF001
    asyncio.run(browser.begin_auth_signin())
    assert context.pages[0].goto_calls == [MICROSOFT_AUTH_BOOTSTRAP_URL]
    assert context.pages[0].sign_in_clicks == 0
    assert context.new_page_calls == 0


# --------------------------------------------------------------------------
# AUTH-113: begin-signin landing verification (fail-closed on about:blank / stale)
# --------------------------------------------------------------------------


def test_landing_on_approved_auth_origin_succeeds() -> None:
    # AUTH-113: when the dedicated page actually lands on the approved Microsoft
    # auth origin, begin-signin returns without raising. Reuse the existing
    # planner_web page (single-page topology) so the navigated page is pages[0].
    context = _FakeContext([_FakePage("https://planner.cloud.microsoft/")])
    browser = _started_production_browser()
    browser._context = context  # noqa: SLF001
    asyncio.run(browser.begin_auth_signin())
    assert context.pages[0].sign_in_clicks == 1
    assert context.pages[0].goto_calls == []
    assert context.pages[0].url == "https://login.microsoftonline.com/"
    assert context.new_page_calls == 0


def test_landing_still_about_blank_fails_closed() -> None:
    # AUTH-113 (the reported defect): the page remained about:blank after the
    # single navigation (aborted/stale dedicated page), so begin-signin MUST NOT
    # report success. It fails closed even though the source classifier accepted
    # the neutral placeholder up front.
    context = _FakeContext([_FakePage("about:blank", landing_url="about:blank")])
    browser = _started_production_browser()
    browser._context = context  # noqa: SLF001
    with pytest.raises(PolicyDenied):
        asyncio.run(browser.begin_auth_signin())
    # The navigation DID happen (Playwright returned the stale page), but the
    # landing gate refused to report success.
    assert context.pages[0].goto_calls == [MICROSOFT_AUTH_BOOTSTRAP_URL]
    assert context.new_page_calls == 0


def test_landing_on_neutral_placeholder_fails_closed() -> None:
    # AUTH-113: a page that navigates to chrome://newtab (still neutral) is NOT
    # an approved auth origin and must fail closed.
    context = _FakeContext([_FakePage("about:blank", landing_url="chrome://newtab")])
    browser = _started_production_browser()
    browser._context = context  # noqa: SLF001
    with pytest.raises(PolicyDenied):
        asyncio.run(browser.begin_auth_signin())


def test_landing_on_non_approved_origin_fails_closed() -> None:
    # AUTH-113: a blocked/stray redirect to an arbitrary web origin must fail
    # closed, never reporting target_class=microsoft_auth.
    context = _FakeContext([_FakePage("about:blank", landing_url="https://example.com/blocked")])
    browser = _started_production_browser()
    browser._context = context  # noqa: SLF001
    with pytest.raises(PolicyDenied):
        asyncio.run(browser.begin_auth_signin())


def test_landing_gate_uses_navigated_page_not_stale_reference() -> None:
    # AUTH-113: the gate reads url from the SAME page object that was navigated.
    # If the context held a stale about:blank page that was reused, the check is
    # against its post-goto url, not a cached snapshot.
    stale = _FakePage("about:blank", landing_url="about:blank")
    context = _FakeContext([stale])
    browser = _started_production_browser()
    browser._context = context  # noqa: SLF001
    # Reused neutral page whose goto leaves it on about:blank -> fails closed.
    with pytest.raises(PolicyDenied):
        asyncio.run(browser.begin_auth_signin())
    assert stale.goto_calls == [MICROSOFT_AUTH_BOOTSTRAP_URL]


@pytest.mark.parametrize(
    "landing_url",
    [
        "https://login.microsoftonline.com/",
        "https://login.live.com/",
        "https://login.microsoft.com/",
        "https://account.microsoft.com/",
        "https://entra.microsoft.com/",
    ],
)
def test_approved_auth_landing_hosts_are_accepted(landing_url: str) -> None:
    # AUTH-113: every host in the closed auth-origin allowlist lands successfully.
    context = _FakeContext([_FakePage("about:blank", landing_url=landing_url)])
    browser = _started_production_browser()
    browser._context = context  # noqa: SLF001
    asyncio.run(browser.begin_auth_signin())
    assert context.pages[0].goto_calls == [MICROSOFT_AUTH_BOOTSTRAP_URL]
    assert context.pages[0].url == landing_url


async def test_route_reports_success_only_on_approved_landing(live_env) -> None:
    # AUTH-113 end-to-end at the route: a real browser whose dedicated page
    # still reports about:blank after begin-signin MUST NOT return 200 /
    # target_class=microsoft_auth. The route maps PolicyDenied -> 503.
    class _StaleLandingBrowser:
        def __init__(self) -> None:
            profile_dir, _h, _m = browser_runtime_settings()
            self._inner = _started_production_browser()
            self._inner._context = _FakeContext(  # noqa: SLF001
                [_FakePage("about:blank", landing_url="about:blank")]
            )
            self._inner.config = BrowserConfig(profile_dir=profile_dir, mode="live")

        @property
        def started(self) -> bool:
            return True

        def is_dedicated_persistent_profile(self) -> bool:
            return True

        def begin_signin_source_permitted(self) -> bool:
            return True

        def auth_origin_approved(self) -> bool:
            return True

        def common_auth_attested(self) -> bool:
            return False

        def full_attested(self) -> bool:
            return False

        def ensure_live_allowed(self, operation: str) -> None:
            from planner_mcp.errors import UiContractUnattested

            raise UiContractUnattested(f"blocked {operation}")

        async def begin_auth_signin(self) -> None:
            # Mirror production source/state checks then drive the REAL
            # production transition, which now applies the AUTH-113 landing gate.
            from m365_browser_worker.bootstrap_navigation import (
                evaluate_microsoft_auth_target,
            )

            target_decision = evaluate_microsoft_auth_target()
            if not target_decision.allowed:
                from planner_mcp.errors import PolicyDenied

                raise PolicyDenied("egress denied", operation="auth_begin_signin")
            await self._inner.begin_auth_signin()

    app = create_app(browser=_StaleLandingBrowser())  # type: ignore[arg-type]
    async with _client(app) as client:
        response = await client.post(BEGIN_SIGNIN_PATH)
    assert response.status_code == 503
    assert response.json()["detail"]["error"] == "POLICY_DENIED"
    assert "microsoft_auth" not in response.text.lower()
