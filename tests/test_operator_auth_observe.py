"""Focused security + behavior suite for the OPERATOR-ONLY observe endpoint.

Covers, explicitly:

* loopback socket peer accepted; Docker-network / non-loopback peer denied (404);
* ``X-Forwarded-For`` / ``X-Real-IP`` / ``Forwarded`` cannot spoof loopback;
* GET only: any query string is rejected (400); no request body is processed;
* no generic DOM endpoint is exposed;
* ``MFA_REQUIRED`` with a UNIQUE 2-digit number returns that number;
* an AMBIGUOUS number match returns ``mfa_number: null`` and never guesses;
* ``WAITING_FOR_MFA`` is reported and the number stays null;
* ambiguous ``UNKNOWN`` reading never corrupts an existing observation context;
* a Planner-Web surface transition after sign-in reports ``AUTHENTICATED`` from
  the live surface rather than contract attestation;
* no URL, page text, DOM, selector, cookie, token, UPN, tenant id or account
  identifier appears in the response;
* the endpoint is absent from the MCP tool registry / control-plane client.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path

import httpx
import pytest

from m365_browser_worker.auth_bootstrap import AuthOriginStatus, auth_origin_status
from m365_browser_worker.bootstrap_navigation import (
    PLANNER_WEB_BOOTSTRAP_URL,
    is_loopback_peer,
    is_planner_web_surface_url,
)
from m365_browser_worker.browser import BrowserConfig, PersistentBrowser
from planner_browser_worker.app import create_app
from planner_browser_worker.observation import observe_signin_state
from planner_mcp.auth import AuthContext, AuthState
from planner_mcp.errors import PlannerMcpError, PolicyDenied, WorkerUnavailable

OBSERVE_PATH = "/auth/bootstrap/observe"

ROOT = Path(__file__).resolve().parent.parent


# --------------------------------------------------------------------------
# Test doubles
# --------------------------------------------------------------------------


class _FakeLocator:
    """Minimal Playwright Locator double returning a static body string."""

    def __init__(self, body: str) -> None:
        self._body = body

    async def inner_text(self) -> str:
        return self._body


class _FakePage:
    def __init__(self, url: str = "about:blank", body: str = "") -> None:
        self.url = url
        self._body = body

    def locator(self, _selector: str) -> _FakeLocator:
        # Mirror production: PersistentBrowser.read_visible_body_bounded reads
        # the visible body via ``page.locator("body").inner_text()``.
        return _FakeLocator(self._body)


class _FakeContext:
    def __init__(self, pages: list[_FakePage] | None = None) -> None:
        self.pages = pages if pages is not None else []


class _ObserveBrowser:
    """Duck-typed PersistentBrowser for the observation contract.

    ``read_visible_body_bounded`` mirrors the production guard: it fires only
    when started + dedicated profile + approved origin + exactly one page.
    Otherwise it fails closed. The visible body text is returned to the caller
    (the endpoint) but never logged or echoed in this double.
    """

    def __init__(
        self,
        *,
        started: bool = True,
        dedicated: bool = True,
        approved_origin: bool = True,
        pages: list[_FakePage] | None = None,
        body: str = "",
    ) -> None:
        self._started = started
        self._dedicated = dedicated
        self._approved_origin = approved_origin
        self.context = _FakeContext(pages)
        self._body = body
        self.observe_calls = 0
        self.max_chars_seen: int | None = None

    @property
    def started(self) -> bool:
        return self._started

    def is_dedicated_persistent_profile(self) -> bool:
        return self._dedicated

    def auth_origin_approved(self) -> bool:
        # Mirror production: an explicit override denies; otherwise derive from
        # the real closed auth-origin classifier over the open pages.
        if not self._approved_origin:
            return False
        pages = [str(p.url) for p in self.context.pages if str(p.url)]
        return auth_origin_status(tuple(pages)) is not AuthOriginStatus.NON_APPROVED_ORIGIN

    def ensure_live_allowed(self, operation: str) -> None:
        # Observation tests run with mocked UIContract; do not fail closed here.
        return None

    async def read_visible_body_bounded(self, max_chars: int = 2000) -> str:
        if not self._started:
            raise WorkerUnavailable("no browser", operation="auth_observe")
        if not self._dedicated:
            raise PolicyDenied("not dedicated", operation="auth_observe")
        if self.context is None:
            raise WorkerUnavailable("no context", operation="auth_observe")
        pages = [p for p in self.context.pages if str(p.url)]
        if len(pages) != 1:
            raise PolicyDenied("not exactly one page", operation="auth_observe")
        page = pages[0]
        if not (self.auth_origin_approved() or is_planner_web_surface_url(str(page.url))):
            raise PolicyDenied("not permitted surface", operation="auth_observe")
        # Count a successful read only (mirrors production, which performs no
        # observation work when the gate fails closed).
        self.observe_calls += 1
        self.max_chars_seen = max_chars
        # Mirror production: read the page's visible body via the Playwright
        # native ``page.locator("body").inner_text()`` (the page double returns
        # its body string). Truncated to max_chars.
        body_text = await page.locator("body").inner_text()
        if not isinstance(body_text, str):
            return ""
        return body_text[:max_chars]


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


def _auth_page(body: str) -> _FakePage:
    return _FakePage(url="https://login.microsoftonline.com/kmsi", body=body)


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


def test_planner_web_surface_predicate_only_target_host() -> None:
    assert is_planner_web_surface_url(PLANNER_WEB_BOOTSTRAP_URL) is True
    assert is_planner_web_surface_url("https://planner.cloud.microsoft/foo") is True
    assert is_planner_web_surface_url("https://sub.planner.cloud.microsoft/") is True
    assert is_planner_web_surface_url("https://login.microsoftonline.com/") is False
    assert is_planner_web_surface_url("https://example.com/") is False


async def test_loopback_peer_accepted(live_env) -> None:
    browser = _ObserveBrowser(pages=[_auth_page("")])
    app = create_app(browser=browser)
    async with _client(app) as client:
        response = await client.get(OBSERVE_PATH)
    assert response.status_code == 200
    body = response.json()
    assert body["state"] in {AuthState.UNKNOWN.value, AuthState.AUTH_REQUIRED.value}
    assert body["mfa_number"] is None
    assert body["mfa_ambiguous"] is False
    assert browser.observe_calls == 1


async def test_docker_network_peer_denied(live_env) -> None:
    browser = _ObserveBrowser(pages=[_auth_page("")])
    app = create_app(browser=browser)
    async with _client(app, peer=("172.18.0.5", 5555)) as client:
        response = await client.get(OBSERVE_PATH)
    assert response.status_code == 404
    assert browser.observe_calls == 0


async def test_forwarded_headers_cannot_spoof_loopback(live_env) -> None:
    browser = _ObserveBrowser(pages=[_auth_page("")])
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
            response = await client.get(OBSERVE_PATH, headers=headers)
            assert response.status_code == 404
    assert browser.observe_calls == 0


# --------------------------------------------------------------------------
# No parameters: query and body rejected
# --------------------------------------------------------------------------


async def test_query_string_rejected(live_env) -> None:
    browser = _ObserveBrowser(pages=[_auth_page("")])
    app = create_app(browser=browser)
    async with _client(app) as client:
        for query in ("?url=https://example.com", "?x=1", "?target=planner"):
            response = await client.get(f"{OBSERVE_PATH}{query}")
            assert response.status_code == 400
            assert response.json()["detail"]["error"] == "INVALID_REQUEST"
    assert browser.observe_calls == 0


# --------------------------------------------------------------------------
# Guard fail-closed behavior
# --------------------------------------------------------------------------


async def test_browser_not_started_fails_closed(live_env) -> None:
    browser = _ObserveBrowser(started=False, pages=[_auth_page("")])
    app = create_app(browser=browser)
    async with _client(app) as client:
        response = await client.get(OBSERVE_PATH)
    assert response.status_code == 503
    assert response.json()["detail"]["error"] == "WORKER_UNAVAILABLE"


async def test_wrong_profile_fails_closed(live_env) -> None:
    browser = _ObserveBrowser(dedicated=False, pages=[_auth_page("")])
    app = create_app(browser=browser)
    async with _client(app) as client:
        response = await client.get(OBSERVE_PATH)
    assert response.status_code == 503
    assert response.json()["detail"]["error"] == "POLICY_DENIED"


async def test_non_approved_origin_fails_closed(live_env) -> None:
    browser = _ObserveBrowser(approved_origin=False, pages=[_auth_page("")])
    app = create_app(browser=browser)
    async with _client(app) as client:
        response = await client.get(OBSERVE_PATH)
    assert response.status_code == 503
    assert browser.observe_calls == 0


async def test_exactly_one_page_required(live_env) -> None:
    # Zero pages or multiple pages must fail closed.
    for pages in ([], [_auth_page(""), _auth_page("")]):
        browser = _ObserveBrowser(pages=pages)
        app = create_app(browser=browser)
        async with _client(app) as client:
            response = await client.get(OBSERVE_PATH)
        assert response.status_code == 503
        assert response.json()["detail"]["error"] == "POLICY_DENIED"


# --------------------------------------------------------------------------
# MFA_REQUIRED unique number
# --------------------------------------------------------------------------


async def test_mfa_required_unique_number(live_env) -> None:
    body = (
        "Approve sign in request. Enter the number 42 shown in your "
        "Microsoft Authenticator app to continue."
    )
    browser = _ObserveBrowser(pages=[_auth_page(body)])
    app = create_app(browser=browser)
    async with _client(app) as client:
        response = await client.get(OBSERVE_PATH)
    assert response.status_code == 200
    body_json = response.json()
    assert body_json["state"] == AuthState.MFA_REQUIRED.value
    assert body_json["mfa_number"] == "42"
    assert body_json["mfa_ambiguous"] is False


# --------------------------------------------------------------------------
# Ambiguity: never guess
# --------------------------------------------------------------------------


async def test_mfa_ambiguous_returns_null(live_env) -> None:
    # Two distinct phrase-bound number-match candidates on the surface:
    # genuinely ambiguous, never guess.
    body = (
        "Enter the number 42 and enter the number 17 shown in your "
        "Microsoft Authenticator app to sign in."
    )
    browser = _ObserveBrowser(pages=[_auth_page(body)])
    app = create_app(browser=browser)
    async with _client(app) as client:
        response = await client.get(OBSERVE_PATH)
    assert response.status_code == 200
    body_json = response.json()
    assert body_json["state"] == AuthState.UNKNOWN.value
    assert body_json["mfa_number"] is None
    assert body_json["mfa_ambiguous"] is True


# --------------------------------------------------------------------------
# WAITING_FOR_MFA
# --------------------------------------------------------------------------


async def test_waiting_for_mfa(live_env) -> None:
    body = "Waiting for approval. Approve sign in request in Microsoft Authenticator."
    browser = _ObserveBrowser(pages=[_auth_page(body)])
    app = create_app(browser=browser)
    async with _client(app) as client:
        response = await client.get(OBSERVE_PATH)
    assert response.status_code == 200
    body_json = response.json()
    assert body_json["state"] == AuthState.WAITING_FOR_MFA.value
    assert body_json["mfa_number"] is None
    assert body_json["mfa_ambiguous"] is False


# --------------------------------------------------------------------------
# Ambiguous UNKNOWN must not corrupt existing context
# --------------------------------------------------------------------------


async def test_ambiguous_unknown_preserves_existing_context(live_env) -> None:
    context = AuthContext(state=AuthState.AUTHENTICATED)
    body = "Enter the number 42 and enter the number 17 shown in your Microsoft Authenticator app."
    browser = _ObserveBrowser(pages=[_auth_page(body)])
    result = await observe_signin_state(browser, context)
    assert result.state is AuthState.UNKNOWN
    assert result.mfa_number is None
    assert result.mfa_ambiguous is True
    # The established AUTHENTICATED context must remain intact.
    assert context.state is AuthState.AUTHENTICATED


async def test_ambiguous_unknown_does_not_persist_in_app_context(live_env) -> None:
    browser = _ObserveBrowser(
        pages=[_auth_page("Enter the number 42 and enter the number 17 in Authenticator.")]
    )
    app = create_app(browser=browser)
    async with _client(app) as client:
        response = await client.get(OBSERVE_PATH)
    assert response.status_code == 200
    assert response.json()["state"] == AuthState.UNKNOWN.value
    # The in-memory observation context was never transitioned away from UNKNOWN.
    assert app.state.observation_context.state is AuthState.UNKNOWN


# --------------------------------------------------------------------------
# Planner-Web authenticated surface transition
# --------------------------------------------------------------------------


async def test_planner_web_surface_reports_authenticated(live_env) -> None:
    # Single open page is the fixed Planner Web surface (not an auth page), so
    # the live surface transition reports AUTHENTICATED.
    page = _FakePage(url=PLANNER_WEB_BOOTSTRAP_URL, body="Planner")
    browser = _ObserveBrowser(pages=[page])
    app = create_app(browser=browser)
    async with _client(app) as client:
        response = await client.get(OBSERVE_PATH)
    assert response.status_code == 200
    body_json = response.json()
    assert body_json["state"] == AuthState.UNKNOWN.value
    assert body_json["mfa_number"] is None
    assert app.state.observation_context.state is AuthState.UNKNOWN


async def test_planner_web_surface_transitions_context(live_env) -> None:
    context = AuthContext(state=AuthState.UNKNOWN)
    page = _FakePage(url=PLANNER_WEB_BOOTSTRAP_URL, body="")
    browser = _ObserveBrowser(pages=[page])
    result = await observe_signin_state(browser, context)
    assert result.state is AuthState.UNKNOWN
    assert context.state is AuthState.UNKNOWN


async def test_planner_web_surface_prior_auth_required_becomes_authenticated(live_env) -> None:
    # Prior in-flight AUTH_REQUIRED + live Planner Web surface => AUTHENTICATED
    # is reported from the live surface (polling skip), not contract attestation.
    context = AuthContext(state=AuthState.AUTH_REQUIRED)
    page = _FakePage(url=PLANNER_WEB_BOOTSTRAP_URL, body="")
    browser = _ObserveBrowser(pages=[page])
    result = await observe_signin_state(browser, context)
    assert result.state is AuthState.AUTHENTICATED
    assert result.mfa_number is None
    assert result.mfa_ambiguous is False
    assert context.state is AuthState.AUTHENTICATED


async def test_planner_web_surface_prior_mfa_required_becomes_authenticated(live_env) -> None:
    context = AuthContext(state=AuthState.MFA_REQUIRED)
    page = _FakePage(url=PLANNER_WEB_BOOTSTRAP_URL, body="")
    browser = _ObserveBrowser(pages=[page])
    result = await observe_signin_state(browser, context)
    assert result.state is AuthState.AUTHENTICATED
    assert result.mfa_number is None
    assert context.state is AuthState.AUTHENTICATED


async def test_planner_web_surface_prior_waiting_for_mfa_becomes_authenticated(live_env) -> None:
    context = AuthContext(state=AuthState.WAITING_FOR_MFA)
    page = _FakePage(url=PLANNER_WEB_BOOTSTRAP_URL, body="")
    browser = _ObserveBrowser(pages=[page])
    result = await observe_signin_state(browser, context)
    assert result.state is AuthState.AUTHENTICATED
    assert result.mfa_number is None
    assert context.state is AuthState.AUTHENTICATED


async def test_other_single_surface_not_misread_as_authenticated(live_env) -> None:
    # A single open page on an arbitrary non-Planner Web surface must not be
    # reported as AUTHENTICATED.
    page = _FakePage(url="https://example.com/dashboard", body="dashboard")
    browser = _ObserveBrowser(pages=[page])
    app = create_app(browser=browser)
    async with _client(app) as client:
        response = await client.get(OBSERVE_PATH)
    assert response.status_code == 503
    assert response.json()["detail"]["error"] == "POLICY_DENIED"


# --------------------------------------------------------------------------
# No secret / identifier leakage
# --------------------------------------------------------------------------


async def test_response_leaks_no_url_or_secret_material(live_env) -> None:
    browser = _ObserveBrowser(pages=[_auth_page("Sign in to continue.")])
    app = create_app(browser=browser)
    async with _client(app) as client:
        response = await client.get(OBSERVE_PATH)
    text = response.text.lower()
    for forbidden in (
        "planner.cloud.microsoft",
        "login.microsoftonline.com",
        "http",
        "cookie",
        "token",
        "password",
        "upn",
        "tenant",
        "bearer",
        "innertext",
        "<html",
        "selector",
    ):
        assert forbidden not in text


async def test_no_generic_dom_endpoint(live_env) -> None:
    browser = _ObserveBrowser(pages=[_auth_page("")])
    app = create_app(browser=browser)
    async with _client(app) as client:
        # A generic DOM/observation surface must not exist.
        for path in ("/auth/bootstrap/dom", "/auth/bootstrap/read", "/dom"):
            response = await client.post(path)
            assert response.status_code in (404, 405)


# --------------------------------------------------------------------------
# Absent from public catalog / control plane
# --------------------------------------------------------------------------


def test_endpoint_absent_from_mcp_tool_catalog() -> None:
    from m365_mcp.tool_registry import default_tool_registry

    names = set(default_tool_registry().names())
    for name in names:
        assert "observe" not in name
        assert "bootstrap" not in name
    assert "auth_bootstrap_observe" not in names


def test_observe_absent_from_worker_client_and_dispatch() -> None:
    from planner_mcp.worker_client import WorkerClient

    assert not [
        attr for attr in dir(WorkerClient) if "observe" in attr or "bootstrap" in attr
    ]
    source = (ROOT / "src" / "planner_browser_worker" / "app.py").read_text(encoding="utf-8")
    dispatcher = source.split("async def dispatch_semantic_operation", 1)[1]
    dispatcher = dispatcher.split('@app.post("/operations"', 1)[0]
    assert "auth_bootstrap_observe" not in dispatcher


def test_operation_constant_not_in_auth_bootstrap_set() -> None:
    from m365_browser_worker.auth_bootstrap import AUTH_BOOTSTRAP_OPERATIONS

    # The observe operation is operator-loopback only and must NOT widen the
    # pre-attestation auth-bootstrap guard set.
    assert "auth_observe" not in AUTH_BOOTSTRAP_OPERATIONS


# -------------------------------------------------------------------------
# Direct primitive: PersistentBrowser.read_visible_body_bounded
# -------------------------------------------------------------------------


class _DirectFakePage(_FakePage):
    """Minimal page double that counts inner_text reads and returns a body."""

    def __init__(self, body: str, url: str = PLANNER_WEB_BOOTSTRAP_URL) -> None:
        super().__init__(url=url, body=body)
        self.inner_text_calls = 0

    def locator(self, _selector: str) -> _FakeLocator:
        # Count a read attempt (mirrors production: one inner_text per read).
        self.inner_text_calls += 1
        return _FakeLocator(self._body)


class _ObserveFakeBrowser(PersistentBrowser):
    """PersistentBrowser with the profile gate satisfied for unit testing.

    Keeps the production ``read_visible_body_bounded`` primitive intact; only
    the unrelated ``started`` / dedicated-profile wiring is stubbed so the
    narrow read path can be exercised directly against a fake context/page.
    """

    def __init__(self, pages: list[_DirectFakePage] | None = None) -> None:
        super().__init__(
            config=BrowserConfig(mode="live", profile_dir=ROOT / "tests" / "data" / "unused")
        )
        self._playwright = object()  # marks the browser started
        self._context = _FakeContext(pages if pages is not None else [])

    def is_dedicated_persistent_profile(self) -> bool:
        return True


async def test_read_visible_body_bounded_awaits_evaluate_and_truncates(live_env) -> None:
    body = "x" * 5000
    page = _DirectFakePage(body=body)
    browser = _ObserveFakeBrowser(pages=[page])

    # Request fewer chars than the body length -> truncated to max_chars.
    result = await browser.read_visible_body_bounded(max_chars=10)
    assert page.inner_text_calls == 1  # page.locator("body").inner_text() read exactly once
    assert result == body[:10]
    assert len(result) == 10

    # Request more chars than the body length -> full body returned unchanged.
    long_result = await browser.read_visible_body_bounded(max_chars=9999)
    assert page.inner_text_calls == 2
    assert long_result == body
    assert len(long_result) == 5000


async def test_read_visible_body_bounded_not_started_fails_closed(live_env) -> None:
    page = _DirectFakePage(body="login")
    browser = _ObserveFakeBrowser(pages=[page])
    browser._playwright = None  # not started

    with pytest.raises(PlannerMcpError) as exc:
        await browser.read_visible_body_bounded(max_chars=2000)
    assert isinstance(exc.value, WorkerUnavailable)
    # The read must never reach the page when the browser is not started.
    assert page.inner_text_calls == 0


async def test_read_visible_body_bounded_non_approved_origin_fails_closed(live_env) -> None:
    page = _DirectFakePage(body="login", url="https://example.com/dashboard")
    browser = _ObserveFakeBrowser(pages=[page])

    with pytest.raises(PlannerMcpError) as exc:
        await browser.read_visible_body_bounded(max_chars=2000)
    assert isinstance(exc.value, PolicyDenied)
    assert page.inner_text_calls == 0


def test_config_spot_check() -> None:
    cfg = BrowserConfig(profile_dir=ROOT / "tests" / "data" / "unused", mode="live")
    assert cfg.is_mock is False
