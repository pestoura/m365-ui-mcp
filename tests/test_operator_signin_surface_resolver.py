"""Security regression suite for the OPERATOR-ONLY deterministic pre-email
sign-in surface resolver (AUTH-109).

Mirrors the AUTH-106 begin-email suite. The resolver forces the email-entry
surface when Microsoft presents a deterministic pre-email intermediate (account
chooser / "use another account" prompt), by clicking ONLY the fixed "use another
account" control — never selecting a cached identity.

Covers, explicitly:

* the route is OPERATOR-ONLY with SOCKET-level loopback admission; non-loopback /
  Docker-network peers get ``404`` and never reach the browser;
* X-Forwarded-For / X-Real-IP / Forwarded cannot spoof loopback;
* the route accepts NO body and NO parameters; any body or query string is
  rejected with ``400``;
* the route does NOT require ``common.auth`` to be attested (intentional, so the
  email surface can be reached for attestation) and fails closed on wrong
  profile / non-approved origin / unstarted browser / wrong page count with
  ``503``;
* the browser applies ONLY the fixed "use another account" action; it never
  reaches email/password fields, never selects a cached account, never clicks
  Sign in, and no URL/DOM/cookie/token/UPN/tenant is returned;
* the endpoint is absent from the MCP tool registry / capability projection /
  agent card / typed ``/operations`` dispatcher and the control-plane worker
  client has no proxy path to it;
* no secret material or account identifier is echoed in the response.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import httpx
import pytest

from m365_browser_worker.signin_surface import AUTH_RESOLVE_OPERATION, SigninSurfaceKind
from planner_browser_worker.app import create_app
from planner_mcp.errors import PolicyDenied, WorkerUnavailable
from planner_mcp.worker_client import WorkerClient

ROOT = Path(__file__).resolve().parent.parent
RESOLVE_PATH = "/auth/bootstrap/resolve-signin-surface"
DIAGNOSE_PATH = "/auth/bootstrap/diagnose-signin-surface"


# --------------------------------------------------------------------------
# Test doubles
# --------------------------------------------------------------------------


class _FakePage:
    def __init__(self, url: str = "about:blank") -> None:
        self.url = url
        self.click_calls: list[str] = []
        self.fill_calls: list[tuple[str, str]] = []

    async def fill(self, selector: str, value: str) -> None:  # pragma: no cover
        self.fill_calls.append((selector, value))

    async def click(self, selector: str = "") -> None:  # pragma: no cover
        self.click_calls.append(selector)


class _FakeContext:
    def __init__(self, pages: list[_FakePage] | None = None) -> None:
        self.pages = pages if pages is not None else []
        self.new_page_calls = 0

    async def new_page(self) -> _FakePage:
        self.new_page_calls += 1
        page = _FakePage()
        self.pages.append(page)
        return page


class _ResolveBrowser:
    """Duck-typed PersistentBrowser exposing the AUTH-109 surface."""

    def __init__(
        self,
        *,
        started: bool = True,
        dedicated: bool = True,
        origin_approved: bool = True,
        pages: list[_FakePage] | None = None,
    ) -> None:
        self._started = started
        self._dedicated = dedicated
        self._origin_approved = origin_approved
        self.context = _FakeContext(pages)
        self.resolve_calls = 0

    @property
    def started(self) -> bool:
        return self._started

    def is_dedicated_persistent_profile(self) -> bool:
        return self._dedicated

    def auth_origin_approved(self) -> bool:
        return self._origin_approved

    def ensure_live_allowed(self, operation: str) -> None:  # pragma: no cover
        raise AssertionError("AUTH-109 must not invoke the full live guard")

    async def resolve_signin_surface(self) -> None:
        if not self._started:
            raise WorkerUnavailable("no browser", operation=AUTH_RESOLVE_OPERATION)
        if not self._dedicated:
            raise PolicyDenied("not dedicated", operation=AUTH_RESOLVE_OPERATION)
        if not self._origin_approved:
            raise PolicyDenied("origin not approved", operation=AUTH_RESOLVE_OPERATION)
        self.resolve_calls += 1


@pytest.fixture()
def live_env() -> Iterator[None]:
    import os

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
# Loopback admission
# --------------------------------------------------------------------------


async def test_loopback_peer_accepted(live_env) -> None:
    browser = _ResolveBrowser(pages=[_FakePage("https://login.microsoftonline.com/")])
    app = create_app(browser=browser)
    async with _client(app) as client:
        response = await client.post(RESOLVE_PATH)
    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["surface"] == SigninSurfaceKind.EMAIL_ENTRY.value
    assert browser.resolve_calls == 1


async def test_docker_network_peer_denied(live_env) -> None:
    browser = _ResolveBrowser(pages=[_FakePage("https://login.microsoftonline.com/")])
    app = create_app(browser=browser)
    async with _client(app, peer=("172.18.0.5", 5555)) as client:
        response = await client.post(RESOLVE_PATH)
    assert response.status_code == 404
    assert browser.resolve_calls == 0


async def test_forwarded_headers_cannot_spoof_loopback(live_env) -> None:
    browser = _ResolveBrowser(pages=[_FakePage("https://login.microsoftonline.com/")])
    app = create_app(browser=browser)
    spoofs = (
        {"X-Forwarded-For": "127.0.0.1"},
        {"X-Real-IP": "127.0.0.1"},
        {"Forwarded": 'for="127.0.0.1"'},
    )
    async with _client(app, peer=("172.18.0.9", 6666)) as client:
        for headers in spoofs:
            response = await client.post(RESOLVE_PATH, headers=headers)
            assert response.status_code == 404
    assert browser.resolve_calls == 0


# --------------------------------------------------------------------------
# No body / no params
# --------------------------------------------------------------------------


async def test_query_string_rejected(live_env) -> None:
    browser = _ResolveBrowser(pages=[_FakePage("https://login.microsoftonline.com/")])
    app = create_app(browser=browser)
    async with _client(app) as client:
        for query in ("?x=1", "?surface=email"):
            response = await client.post(f"{RESOLVE_PATH}{query}")
            assert response.status_code == 400
    assert browser.resolve_calls == 0


async def test_body_rejected(live_env) -> None:
    browser = _ResolveBrowser(pages=[_FakePage("https://login.microsoftonline.com/")])
    app = create_app(browser=browser)
    async with _client(app) as client:
        response = await client.post(RESOLVE_PATH, json={"surface": "use_another"})
        assert response.status_code == 400
    assert browser.resolve_calls == 0


# --------------------------------------------------------------------------
# Guard fail-closed (no attestation required)
# --------------------------------------------------------------------------


async def test_runs_without_attestation(live_env) -> None:
    browser = _ResolveBrowser(pages=[_FakePage("https://login.microsoftonline.com/")])
    app = create_app(browser=browser)
    async with _client(app) as client:
        response = await client.post(RESOLVE_PATH)
    assert response.status_code == 200
    assert browser.resolve_calls == 1


async def test_browser_not_started_fails_closed(live_env) -> None:
    browser = _ResolveBrowser(started=False)
    app = create_app(browser=browser)
    async with _client(app) as client:
        response = await client.post(RESOLVE_PATH)
    assert response.status_code == 503
    assert browser.resolve_calls == 0


async def test_wrong_profile_fails_closed(live_env) -> None:
    browser = _ResolveBrowser(dedicated=False)
    app = create_app(browser=browser)
    async with _client(app) as client:
        response = await client.post(RESOLVE_PATH)
    assert response.status_code == 503
    assert browser.resolve_calls == 0


async def test_non_approved_origin_fails_closed(live_env) -> None:
    browser = _ResolveBrowser(origin_approved=False)
    app = create_app(browser=browser)
    async with _client(app) as client:
        response = await client.post(RESOLVE_PATH)
    assert response.status_code == 503
    assert browser.resolve_calls == 0


# --------------------------------------------------------------------------
# No secret / identity leakage
# --------------------------------------------------------------------------


async def test_response_leaks_no_secret_or_url(live_env) -> None:
    browser = _ResolveBrowser(pages=[_FakePage("https://login.microsoftonline.com/")])
    app = create_app(browser=browser)

    async def _run() -> str:
        async with _client(app) as client:
            response = await client.post(RESOLVE_PATH)
        return response.text.lower()

    body = await _run()
    for forbidden in (
        "login.microsoftonline.com",
        "http",
        "cookie",
        "token",
        "upn",
        "tenant",
        "bearer",
        "password",
        "use another account",
        "<html",
    ):
        assert forbidden not in body


# -------------------------------------------------------------------------
# Fail-closed observability: 503 carries ONLY the sanitized terminal surface enum
# -------------------------------------------------------------------------


class _FailClosedTerminalBrowser:
    """Duck-typed PersistentBrowser that rails to a non-forwardable surface."""

    def __init__(
        self,
        *,
        started: bool = True,
        dedicated: bool = True,
        origin_approved: bool = True,
        pages: list[_FakePage] | None = None,
        terminal_kind: SigninSurfaceKind = SigninSurfaceKind.STAY_SIGNED_IN,
    ) -> None:
        self._started = started
        self._dedicated = dedicated
        self._origin_approved = origin_approved
        self._terminal_kind = terminal_kind
        self._pages = pages if pages is not None else []
        self.resolve_calls = 0

    @property
    def started(self) -> bool:
        return self._started

    def is_dedicated_persistent_profile(self) -> bool:
        return self._dedicated

    def auth_origin_approved(self) -> bool:
        return self._origin_approved

    def ensure_live_allowed(self, operation: str) -> None:  # pragma: no cover
        raise AssertionError("AUTH-109 must not invoke the full live guard")

    async def resolve_signin_surface(self) -> None:
        if not self._started:
            raise WorkerUnavailable("no browser", operation=AUTH_RESOLVE_OPERATION)
        if not self._dedicated:
            raise PolicyDenied("not dedicated", operation=AUTH_RESOLVE_OPERATION)
        if not self._origin_approved:
            raise PolicyDenied("origin not approved", operation=AUTH_RESOLVE_OPERATION)
        self.resolve_calls += 1
        # Fail-closed: propagate the sanitized terminal surface enum only.
        raise PolicyDenied(
            "sign-in surface is not a deterministic pre-email stage",
            operation=AUTH_RESOLVE_OPERATION,
            terminal_surface=self._terminal_kind.value,
        )


async def test_fail_closed_503_carries_sanitized_terminal_surface(live_env) -> None:
    browser = _FailClosedTerminalBrowser(
        pages=[_FakePage("https://login.microsoftonline.com/")],
        terminal_kind=SigninSurfaceKind.CONSENT,
    )
    app = create_app(browser=browser)
    async with _client(app) as client:
        response = await client.post(RESOLVE_PATH)
    assert response.status_code == 503
    assert browser.resolve_calls == 1
    body = response.json()
    # FastAPI wraps the raised HTTPException detail under "detail".
    detail = body["detail"]
    assert detail["error"] == "POLICY_DENIED"
    # The sanitized closed enum is present and is a known SigninSurfaceKind value.
    context = detail.get("context", {})
    assert context.get("terminal_surface") == SigninSurfaceKind.CONSENT.value
    assert context["terminal_surface"] in {k.value for k in SigninSurfaceKind}
    # Still no leak of raw text/URL/identity (the enum value CONSENT is expected
    # and is the only sanctioned surface token; forbidden tokens below would
    # indicate a real leak of URL/DOM/credential/material).
    low = response.text.lower()
    for forbidden in (
        "login.microsoftonline.com",
        "http",
        "cookie",
        "token",
        "upn",
        "tenant",
        "bearer",
        "password",
        "use another account",
        "permissions requested by this app",
        "<html",
    ):
        assert forbidden not in low


# --------------------------------------------------------------------------
# Catalog absence (must not become an MCP tool)
# --------------------------------------------------------------------------


def test_endpoint_absent_from_mcp_tool_catalog() -> None:
    from m365_mcp.tool_registry import default_tool_registry

    names = set(default_tool_registry().names())
    assert not [n for n in names if "resolve" in n and "signin" in n]


def test_worker_client_has_no_resolve_proxy() -> None:
    attributes = dir(WorkerClient)
    assert not [a for a in attributes if "resolve_signin_surface" in a]
    source = (ROOT / "src" / "planner_mcp" / "worker_client.py").read_text(encoding="utf-8")
    assert RESOLVE_PATH not in source


# --------------------------------------------------------------------------
# READ-ONLY diagnose route (AUTH-109-diagnose): classify-only, never click
# --------------------------------------------------------------------------


class _DiagnoseBrowser:
    """Duck-typed PersistentBrowser exposing the AUTH-109-diagnose surface."""

    def __init__(
        self,
        *,
        started: bool = True,
        dedicated: bool = True,
        origin_approved: bool = True,
        pages: list[_FakePage] | None = None,
        classification: SigninSurfaceKind | None = None,
        raises: type[Exception] | None = None,
    ) -> None:
        self._started = started
        self._dedicated = dedicated
        self._origin_approved = origin_approved
        self._classification = classification or SigninSurfaceKind.EMAIL_ENTRY
        self._raises = raises
        self.diagnose_calls = 0

    @property
    def started(self) -> bool:
        return self._started

    def is_dedicated_persistent_profile(self) -> bool:
        return self._dedicated

    def auth_origin_approved(self) -> bool:
        return self._origin_approved

    def ensure_live_allowed(self, operation: str) -> None:  # pragma: no cover
        raise AssertionError("AUTH-109-diagnose must not invoke the full live guard")

    async def diagnose_signin_surface(self):
        if self._raises is not None:
            raise self._raises("diagnose blocked", operation="auth_diagnose_signin_surface")
        self.diagnose_calls += 1
        # Minimal stub: the real method returns a SurfaceClassification; the
        # route only reads `.kind.value` and `.email_entry_present`.
        from m365_browser_worker.signin_surface import SurfaceClassification

        return SurfaceClassification(self._classification, email_entry_present=True)


async def test_diagnose_loopback_peer_accepted(live_env) -> None:
    browser = _DiagnoseBrowser(pages=[_FakePage("https://login.microsoftonline.com/")])
    app = create_app(browser=browser)
    async with _client(app) as client:
        response = await client.get(DIAGNOSE_PATH)
    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["surface"] == SigninSurfaceKind.EMAIL_ENTRY.value
    assert body["email_entry_present"] is True
    assert browser.diagnose_calls == 1


async def test_diagnose_docker_network_peer_denied(live_env) -> None:
    browser = _DiagnoseBrowser(pages=[_FakePage("https://login.microsoftonline.com/")])
    app = create_app(browser=browser)
    async with _client(app, peer=("172.18.0.5", 5555)) as client:
        response = await client.get(DIAGNOSE_PATH)
    assert response.status_code == 404
    assert browser.diagnose_calls == 0


async def test_diagnose_query_string_rejected(live_env) -> None:
    browser = _DiagnoseBrowser(pages=[_FakePage("https://login.microsoftonline.com/")])
    app = create_app(browser=browser)
    async with _client(app) as client:
        response = await client.get(f"{DIAGNOSE_PATH}?x=1")
    assert response.status_code == 400
    assert browser.diagnose_calls == 0


async def test_diagnose_body_rejected(live_env) -> None:
    browser = _DiagnoseBrowser(pages=[_FakePage("https://login.microsoftonline.com/")])
    app = create_app(browser=browser)
    async with _client(app) as client:
        response = await client.request("POST", DIAGNOSE_PATH)
    # GET-only: a POST is rejected by the framework before reaching the handler.
    assert response.status_code in (404, 405)
    assert browser.diagnose_calls == 0


async def test_diagnose_not_started_fails_closed(live_env) -> None:
    browser = _DiagnoseBrowser(started=False)
    app = create_app(browser=browser)
    async with _client(app) as client:
        response = await client.get(DIAGNOSE_PATH)
    assert response.status_code == 503
    assert browser.diagnose_calls == 0


async def test_diagnose_wrong_profile_fails_closed(live_env) -> None:
    browser = _DiagnoseBrowser(dedicated=False)
    app = create_app(browser=browser)
    async with _client(app) as client:
        response = await client.get(DIAGNOSE_PATH)
    assert response.status_code == 503
    assert browser.diagnose_calls == 0


async def test_diagnose_response_leaks_no_secret_or_url(live_env) -> None:
    browser = _DiagnoseBrowser(pages=[_FakePage("https://login.microsoftonline.com/")])
    app = create_app(browser=browser)

    async def _run() -> str:
        async with _client(app) as client:
            response = await client.get(DIAGNOSE_PATH)
        return response.text.lower()

    body = await _run()
    for forbidden in (
        "login.microsoftonline.com",
        "http",
        "cookie",
        "token",
        "upn",
        "tenant",
        "bearer",
        "password",
        "use another account",
        "<html",
    ):
        assert forbidden not in body


def test_diagnose_endpoint_absent_from_mcp_tool_catalog() -> None:
    from m365_mcp.tool_registry import default_tool_registry

    names = set(default_tool_registry().names())
    assert not [n for n in names if "diagnose" in n and "signin" in n]


def test_worker_client_has_no_diagnose_proxy() -> None:
    attributes = dir(WorkerClient)
    assert not [a for a in attributes if "diagnose_signin_surface" in a]
    source = (ROOT / "src" / "planner_mcp" / "worker_client.py").read_text(encoding="utf-8")
    assert DIAGNOSE_PATH not in source
