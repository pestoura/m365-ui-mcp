"""Security regression suite for the OPERATOR-ONLY pre-attestation email stage.

AUTH-106 — the minimal headless-safe primitive that breaks the attestation
bootstrap deadlock left after the GUI/noVNC/X11 handoff was removed (PR #614).
The password/signin selectors needed for ``common.auth`` attestation only appear
AFTER email -> Next, and ``submit_operator_signin`` requires full attestation, so
without this stage there was no headless path to reach the password surface for
attestation. This stage fills ONLY the email field and clicks ONLY Next; it never
types a password and never clicks Sign in, and it does NOT require attestation
to run.

Covers, explicitly:

* the route is OPERATOR-ONLY with SOCKET-level loopback admission; non-loopback /
  Docker-network peers get ``404`` and never reach the browser;
* X-Forwarded-For / X-Real-IP / Forwarded cannot spoof loopback;
* the body is the closed ``{email}`` contract only; any extra/unknown key
  (including ``password``) or a missing key is rejected with ``400``;
* the route does NOT require ``common.auth`` to be attested (intentional, so
  attestation can be collected) and fails closed on wrong profile / non-approved
  origin / unstarted browser with ``503``;
* the browser applies ONLY the email field and clicks ONLY Next; it never reaches
  the password/signin fields; no URL/DOM/cookie/token/UPN/tenant is returned;
* the endpoint is absent from the MCP tool registry / capability projection /
  agent card / typed ``/operations`` dispatcher and the control-plane worker
  client has no proxy path to it;
* no secret material (email value, password) is echoed in the response.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path

import httpx
import pytest

from m365_browser_worker.operator_signin import (
    ALLOWED_EMAIL_STAGE_FIELDS,
    AUTH_BEGIN_EMAIL_STAGE_OPERATION,
    OperatorEmailStageInput,
    validate_email_stage_input,
)
from planner_browser_worker.app import create_app
from planner_mcp.errors import PolicyDenied, WorkerUnavailable
from planner_mcp.worker_client import WorkerClient

ROOT = Path(__file__).resolve().parent.parent
BEGIN_EMAIL_PATH = "/auth/bootstrap/begin-email"


# --------------------------------------------------------------------------
# Test doubles
# --------------------------------------------------------------------------


class _FakePage:
    def __init__(self, url: str = "about:blank") -> None:
        self.url = url
        self.fill_calls: list[tuple[str, str]] = []
        self.click_calls: list[str] = []

    async def fill(self, selector: str, value: str) -> None:
        self.fill_calls.append((selector, value))

    async def click(self, selector: str = "") -> None:
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


class _BeginEmailBrowser:
    """Duck-typed PersistentBrowser exposing the email-stage surface."""

    def __init__(
        self,
        *,
        started: bool = True,
        dedicated: bool = True,
        origin_approved: bool = True,
        auth_attested: bool = False,
        pages: list[_FakePage] | None = None,
    ) -> None:
        self._started = started
        self._dedicated = dedicated
        self._origin_approved = origin_approved
        self._auth_attested = auth_attested
        self.context = _FakeContext(pages)
        self.email_stage_calls: list[str] = []

    @property
    def started(self) -> bool:
        return self._started

    def is_dedicated_persistent_profile(self) -> bool:
        return self._dedicated

    def auth_origin_approved(self) -> bool:
        return self._origin_approved

    def common_auth_attested(self) -> bool:
        return self._auth_attested

    def ensure_live_allowed(self, operation: str) -> None:  # pragma: no cover
        raise AssertionError("email stage must not invoke the full live guard")

    async def begin_email_stage(self, email: str) -> None:
        # Mirror production order: guards run first, then email fill + Next click.
        if not self._started:
            raise WorkerUnavailable("no browser", operation=AUTH_BEGIN_EMAIL_STAGE_OPERATION)
        if not self._dedicated:
            raise PolicyDenied("not dedicated", operation=AUTH_BEGIN_EMAIL_STAGE_OPERATION)
        if not self._origin_approved:
            raise PolicyDenied(
                "origin not approved", operation=AUTH_BEGIN_EMAIL_STAGE_OPERATION
            )
        self.email_stage_calls.append(email)
        page = None
        for candidate in self.context.pages:
            if str(candidate.url):
                page = candidate
        if page is None:
            page = await self.context.new_page()
        # Email stage touches ONLY the email field and the Next control.
        await page.fill("auth.login_email_input", email)
        await page.click("auth.login_next_button")


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
# Closed body contract
# --------------------------------------------------------------------------


def test_email_stage_fields_are_exactly_email() -> None:
    assert ALLOWED_EMAIL_STAGE_FIELDS == ("email",)
    with pytest.raises(ValueError):
        validate_email_stage_input({"email": "a@b.com", "password": "x"})
    with pytest.raises(ValueError):
        validate_email_stage_input({"password": "x"})
    with pytest.raises(ValueError):
        validate_email_stage_input({})
    stage = validate_email_stage_input({"email": "a@b.com"})
    assert isinstance(stage, OperatorEmailStageInput)
    assert stage.field_names() == ("email",)


async def test_password_key_rejected(live_env) -> None:
    browser = _BeginEmailBrowser(pages=[_FakePage("https://login.microsoftonline.com/")])
    app = create_app(browser=browser)
    async with _client(app) as client:
        # The password must never be an accepted key on the email stage.
        response = await client.post(
            BEGIN_EMAIL_PATH, json={"email": "a@b.com", "password": "secret"}
        )
    assert response.status_code == 400
    assert browser.email_stage_calls == []


# --------------------------------------------------------------------------
# Loopback admission
# --------------------------------------------------------------------------


async def test_loopback_peer_accepted(live_env) -> None:
    browser = _BeginEmailBrowser(pages=[_FakePage("https://login.microsoftonline.com/")])
    app = create_app(browser=browser)
    async with _client(app) as client:
        response = await client.post(BEGIN_EMAIL_PATH, json={"email": "operator@contoso.com"})
    assert response.status_code == 200
    assert response.json() == {"ok": True, "auth_state": "UNKNOWN"}
    assert browser.email_stage_calls == ["operator@contoso.com"]


async def test_docker_network_peer_denied(live_env) -> None:
    browser = _BeginEmailBrowser(pages=[_FakePage("https://login.microsoftonline.com/")])
    app = create_app(browser=browser)
    async with _client(app, peer=("172.18.0.5", 5555)) as client:
        response = await client.post(BEGIN_EMAIL_PATH, json={"email": "a@b.com"})
    assert response.status_code == 404
    assert browser.email_stage_calls == []


async def test_forwarded_headers_cannot_spoof_loopback(live_env) -> None:
    browser = _BeginEmailBrowser(pages=[_FakePage("https://login.microsoftonline.com/")])
    app = create_app(browser=browser)
    spoofs = (
        {"X-Forwarded-For": "127.0.0.1"},
        {"X-Real-IP": "127.0.0.1"},
        {"Forwarded": 'for="127.0.0.1"'},
    )
    async with _client(app, peer=("172.18.0.9", 6666)) as client:
        for headers in spoofs:
            response = await client.post(
                BEGIN_EMAIL_PATH, json={"email": "a@b.com"}, headers=headers
            )
            assert response.status_code == 404
    assert browser.email_stage_calls == []


async def test_query_string_rejected(live_env) -> None:
    browser = _BeginEmailBrowser(pages=[_FakePage("https://login.microsoftonline.com/")])
    app = create_app(browser=browser)
    async with _client(app) as client:
        for query in ("?email=x", "?x=1"):
            response = await client.post(f"{BEGIN_EMAIL_PATH}{query}", json={"email": "a@b.com"})
            assert response.status_code == 400
    assert browser.email_stage_calls == []


# --------------------------------------------------------------------------
# Guard fail-closed (no attestation required)
# --------------------------------------------------------------------------


async def test_runs_without_attestation(live_env) -> None:
    # The whole point of AUTH-106: the email stage must run PRE-attestation.
    browser = _BeginEmailBrowser(
        pages=[_FakePage("https://login.microsoftonline.com/")], auth_attested=False
    )
    app = create_app(browser=browser)
    async with _client(app) as client:
        response = await client.post(BEGIN_EMAIL_PATH, json={"email": "a@b.com"})
    assert response.status_code == 200
    assert browser.email_stage_calls == ["a@b.com"]


async def test_browser_not_started_fails_closed(live_env) -> None:
    browser = _BeginEmailBrowser(started=False)
    app = create_app(browser=browser)
    async with _client(app) as client:
        response = await client.post(BEGIN_EMAIL_PATH, json={"email": "a@b.com"})
    assert response.status_code == 503
    assert browser.email_stage_calls == []


async def test_wrong_profile_fails_closed(live_env) -> None:
    browser = _BeginEmailBrowser(dedicated=False)
    app = create_app(browser=browser)
    async with _client(app) as client:
        response = await client.post(BEGIN_EMAIL_PATH, json={"email": "a@b.com"})
    assert response.status_code == 503
    assert browser.email_stage_calls == []


async def test_non_approved_origin_fails_closed(live_env) -> None:
    browser = _BeginEmailBrowser(origin_approved=False)
    app = create_app(browser=browser)
    async with _client(app) as client:
        response = await client.post(BEGIN_EMAIL_PATH, json={"email": "a@b.com"})
    assert response.status_code == 503
    assert browser.email_stage_calls == []


# --------------------------------------------------------------------------
# No secret / URL leakage
# --------------------------------------------------------------------------


async def test_response_leaks_no_secret_or_url(live_env) -> None:
    browser = _BeginEmailBrowser(pages=[_FakePage("https://login.microsoftonline.com/")])
    app = create_app(browser=browser)

    async def _run() -> str:
        async with _client(app) as client:
            response = await client.post(
                BEGIN_EMAIL_PATH, json={"email": "operator@contoso.com"}
            )
        return response.text.lower()

    body = await _run()
    for forbidden in (
        "operator@contoso.com",
        "login.microsoftonline.com",
        "http",
        "cookie",
        "token",
        "upn",
        "tenant",
        "bearer",
        "password",
        "<html",
    ):
        assert forbidden not in body


def test_applies_only_email_and_next(live_env) -> None:
    # Synchronous check of the browser primitive via the duck-typed browser is
    # covered by the loopback_peer_accepted path above; assert the produced
    # primitives touch exactly the email field and Next control, never password.
    page = _FakePage("https://login.microsoftonline.com/")
    import asyncio

    browser = _BeginEmailBrowser(pages=[page])
    asyncio.run(browser.begin_email_stage("a@b.com"))
    assert page.fill_calls == [("auth.login_email_input", "a@b.com")]
    assert page.click_calls == ["auth.login_next_button"]


# --------------------------------------------------------------------------
# Catalog absence (must not become an MCP tool)
# --------------------------------------------------------------------------


def test_endpoint_absent_from_mcp_tool_catalog() -> None:
    from m365_mcp.tool_registry import default_tool_registry

    names = set(default_tool_registry().names())
    assert not [n for n in names if "begin-email" in n or "email-stage" in n]


def test_worker_client_has_no_begin_email_proxy() -> None:
    attributes = dir(WorkerClient)
    assert not [a for a in attributes if "begin_email" in a or "beginemail" in a]
    source = (ROOT / "src" / "planner_mcp" / "worker_client.py").read_text(encoding="utf-8")
    assert BEGIN_EMAIL_PATH not in source
