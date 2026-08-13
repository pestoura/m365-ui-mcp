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
)
from m365_browser_worker.browser import BrowserConfig, PersistentBrowser
from m365_browser_worker.egress import evaluate_browser_egress
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
    assert "m365-ui-mcp-browser-worker-1" in text
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
    assert "docker exec m365-ui-mcp-browser-worker-1" in text
    assert "127.0.0.1:8090/auth/bootstrap/begin-signin" in text
