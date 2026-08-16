"""Security regression suite for the OPERATOR-ONLY auth bootstrap navigation.

Covers, explicitly:

* loopback socket peer accepted; Docker-network / non-loopback peer denied;
* ``X-Forwarded-For`` / ``X-Real-IP`` / ``Forwarded`` cannot spoof loopback;
* any query string and any non-empty body are rejected;
* the target is a FIXED constant: no parameter exists anywhere in the path and
  arbitrary hosts (example.com) are impossible/denied by the egress policy;
* the egress policy is invoked on every navigation and denial fails closed;
* Graph remains denied;
* the endpoint is absent from the MCP tool registry / capability projection /
  agent card / typed ``/operations`` dispatcher and the control-plane worker
  client has no proxy path to it;
* wrong profile / non-approved origin / stopped browser fail closed (503);
* no raw URL, DOM, cookie, token, UPN or tenant id appears in the response;
* exactly ONE navigation happens per call;
* the operator wrapper accepts no URL argument and uses docker exec + loopback.
"""

from __future__ import annotations

import os
import subprocess
from collections.abc import Iterator
from pathlib import Path

import httpx
import pytest

from m365_browser_worker.auth_bootstrap import AUTH_BOOTSTRAP_OPERATIONS
from m365_browser_worker.bootstrap_navigation import (
    AUTH_BOOTSTRAP_NAVIGATE_OPERATION,
    PLANNER_WEB_BOOTSTRAP_URL,
    PLANNER_WEB_TARGET_CLASS,
    evaluate_bootstrap_target,
    is_loopback_peer,
    is_reusable_bootstrap_page,
)
from m365_browser_worker.browser import BrowserConfig, PersistentBrowser
from m365_browser_worker.egress import evaluate_browser_egress
from m365_mcp.tool_registry import default_tool_registry
from planner_browser_worker.app import create_app
from planner_mcp.errors import PolicyDenied, UiContractUnattested, WorkerUnavailable
from planner_mcp.worker_client import WorkerClient

ROOT = Path(__file__).resolve().parent.parent
# Never created or written: the navigation tests inject a duck-typed context.
_UNUSED_PROFILE_DIR = Path(__file__).resolve().parent / "data" / "unused-live-profile"
NAVIGATE_PATH = "/auth/bootstrap/navigate"


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


class _NavBrowser:
    """Duck-typed PersistentBrowser exposing the guard + navigation surface."""

    def __init__(
        self,
        *,
        started: bool = True,
        dedicated: bool = True,
        approved_origin: bool = True,
        full_attested: bool = False,
        auth_attested: bool = False,
        pages: list[_FakePage] | None = None,
    ) -> None:
        self._started = started
        self._dedicated = dedicated
        self._approved_origin = approved_origin
        self._full_attested = full_attested
        self._auth_attested = auth_attested
        self.context = _FakeContext(pages)
        self.navigate_calls = 0
        self.egress_evaluations = 0
        self.deny_egress = False

    @property
    def started(self) -> bool:
        return self._started

    def is_dedicated_persistent_profile(self) -> bool:
        return self._dedicated

    def auth_origin_approved(self) -> bool:
        return self._approved_origin

    def common_auth_attested(self) -> bool:
        return self._auth_attested

    def full_attested(self) -> bool:
        return self._full_attested

    def ensure_live_allowed(self, operation: str) -> None:
        if not self._full_attested:
            raise UiContractUnattested(f"blocked {operation}")

    async def navigate_auth_bootstrap(self) -> None:
        # Mirrors the production ordering: state, then egress policy, then one goto.
        if not self._started:
            raise WorkerUnavailable("no browser", operation=AUTH_BOOTSTRAP_NAVIGATE_OPERATION)
        self.egress_evaluations += 1
        decision = evaluate_bootstrap_target()
        if self.deny_egress or not decision.allowed:
            raise PolicyDenied(
                "denied by egress policy",
                operation=AUTH_BOOTSTRAP_NAVIGATE_OPERATION,
            )
        self.navigate_calls += 1
        page = None
        for candidate in self.context.pages:
            if is_reusable_bootstrap_page(str(candidate.url)):
                page = candidate
                break
        if page is None:
            page = await self.context.new_page()
        await page.goto(PLANNER_WEB_BOOTSTRAP_URL)


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
# Fixed target / no parameters
# --------------------------------------------------------------------------


def test_bootstrap_target_is_the_fixed_planner_constant() -> None:
    assert PLANNER_WEB_BOOTSTRAP_URL == "https://planner.cloud.microsoft/"
    assert PLANNER_WEB_TARGET_CLASS == "planner_web"


def test_fixed_target_is_allowed_by_egress_policy() -> None:
    decision = evaluate_bootstrap_target()
    assert decision.allowed is True
    assert decision == evaluate_browser_egress(PLANNER_WEB_BOOTSTRAP_URL)


def test_navigation_helper_takes_no_target_argument() -> None:
    import inspect

    signature = inspect.signature(PersistentBrowser.navigate_auth_bootstrap)
    assert list(signature.parameters) == ["self"]


def test_arbitrary_and_graph_hosts_remain_denied() -> None:
    for url in (
        "https://example.com/",
        "https://evil.example.com/planner",
        "https://graph.microsoft.com/v1.0/me",
        "https://graph.example.microsoft.com/",
        "http://planner.cloud.microsoft/",
    ):
        assert evaluate_browser_egress(url).allowed is False


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
    browser = _NavBrowser()
    app = create_app(browser=browser)
    async with _client(app) as client:
        response = await client.post(NAVIGATE_PATH)
    assert response.status_code == 200
    assert response.json() == {
        "ok": True,
        "target_class": "planner_web",
        "auth_state": "UNKNOWN",
    }
    assert browser.navigate_calls == 1


async def test_docker_network_peer_denied(live_env) -> None:
    browser = _NavBrowser()
    app = create_app(browser=browser)
    async with _client(app, peer=("172.18.0.5", 5555)) as client:
        response = await client.post(NAVIGATE_PATH)
    assert response.status_code == 404
    assert browser.navigate_calls == 0
    assert browser.egress_evaluations == 0


async def test_forwarded_headers_cannot_spoof_loopback(live_env) -> None:
    browser = _NavBrowser()
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
            response = await client.post(NAVIGATE_PATH, headers=headers)
            assert response.status_code == 404
    assert browser.navigate_calls == 0


# --------------------------------------------------------------------------
# No parameters: query and body rejected
# --------------------------------------------------------------------------


async def test_query_string_rejected(live_env) -> None:
    browser = _NavBrowser()
    app = create_app(browser=browser)
    async with _client(app) as client:
        for query in ("?url=https://example.com", "?x=1", "?target=planner"):
            response = await client.post(f"{NAVIGATE_PATH}{query}")
            assert response.status_code == 400
            assert response.json()["detail"]["error"] == "INVALID_REQUEST"
    assert browser.navigate_calls == 0


async def test_non_empty_body_rejected(live_env) -> None:
    browser = _NavBrowser()
    app = create_app(browser=browser)
    async with _client(app) as client:
        response = await client.post(NAVIGATE_PATH, json={"url": "https://example.com"})
        assert response.status_code == 400
        response = await client.post(NAVIGATE_PATH, content=b"https://example.com")
        assert response.status_code == 400
    assert browser.navigate_calls == 0


# --------------------------------------------------------------------------
# Guard / egress fail-closed behavior
# --------------------------------------------------------------------------


async def test_wrong_profile_fails_closed(live_env) -> None:
    browser = _NavBrowser(dedicated=False)
    app = create_app(browser=browser)
    async with _client(app) as client:
        response = await client.post(NAVIGATE_PATH)
    assert response.status_code == 503
    assert response.json()["detail"]["error"] == "POLICY_DENIED"
    assert browser.navigate_calls == 0


async def test_non_approved_origin_fails_closed(live_env) -> None:
    browser = _NavBrowser(approved_origin=False)
    app = create_app(browser=browser)
    async with _client(app) as client:
        response = await client.post(NAVIGATE_PATH)
    assert response.status_code == 503
    assert browser.navigate_calls == 0


async def test_browser_not_started_fails_closed(live_env) -> None:
    browser = _NavBrowser(started=False)
    app = create_app(browser=browser)
    async with _client(app) as client:
        response = await client.post(NAVIGATE_PATH)
    assert response.status_code == 503
    assert browser.navigate_calls == 0


async def test_egress_policy_invoked_and_denial_fails_closed(live_env) -> None:
    browser = _NavBrowser()
    browser.deny_egress = True
    app = create_app(browser=browser)
    async with _client(app) as client:
        response = await client.post(NAVIGATE_PATH)
    assert response.status_code == 503
    assert browser.egress_evaluations == 1
    assert browser.navigate_calls == 0


async def test_exactly_one_navigation_per_call(live_env) -> None:
    page = _FakePage("about:blank")
    browser = _NavBrowser(pages=[page])
    app = create_app(browser=browser)
    async with _client(app) as client:
        assert (await client.post(NAVIGATE_PATH)).status_code == 200
    assert browser.navigate_calls == 1
    assert page.goto_calls == [PLANNER_WEB_BOOTSTRAP_URL]
    assert browser.context.new_page_calls == 0
    # Idempotent operator action: a second call performs exactly one more
    # navigation. The first page now holds the target (no longer a neutral
    # placeholder), so exactly one additional page is opened — never two.
    async with _client(app) as client:
        assert (await client.post(NAVIGATE_PATH)).status_code == 200
    assert browser.navigate_calls == 2
    assert browser.context.new_page_calls == 1
    assert len(browser.context.pages) == 2
    assert page.goto_calls == [PLANNER_WEB_BOOTSTRAP_URL]
    assert browser.context.pages[1].goto_calls == [PLANNER_WEB_BOOTSTRAP_URL]


async def test_non_neutral_page_is_not_hijacked(live_env) -> None:
    existing = _FakePage("https://login.microsoftonline.com/kmsi")
    browser = _NavBrowser(pages=[existing])
    app = create_app(browser=browser)
    async with _client(app) as client:
        assert (await client.post(NAVIGATE_PATH)).status_code == 200
    assert existing.goto_calls == []
    assert browser.context.new_page_calls == 1
    assert len(browser.context.pages) == 2


def test_reusable_page_predicate_only_neutral_pages() -> None:
    assert is_reusable_bootstrap_page("about:blank") is True
    assert is_reusable_bootstrap_page("chrome://newtab") is True
    assert is_reusable_bootstrap_page("chrome://newtab/?x=1") is True
    assert is_reusable_bootstrap_page("https://planner.cloud.microsoft/") is False
    assert is_reusable_bootstrap_page("https://example.com/") is False


async def test_response_leaks_no_url_or_secret_material(live_env) -> None:
    browser = _NavBrowser()
    app = create_app(browser=browser)
    async with _client(app) as client:
        response = await client.post(NAVIGATE_PATH)
    body = response.text.lower()
    for forbidden in (
        "planner.cloud.microsoft",
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


async def test_navigation_does_not_relax_planner_read_gates(live_env) -> None:
    browser = _NavBrowser()
    app = create_app(browser=browser)
    async with _client(app) as client:
        assert (await client.post(NAVIGATE_PATH)).status_code == 200
        for path in ("/account/context", "/account/license"):
            assert (await client.get(path)).status_code == 503


# --------------------------------------------------------------------------
# Absent from every public catalog / no control-plane proxy
# --------------------------------------------------------------------------


def test_operation_only_in_auth_bootstrap_set() -> None:
    assert AUTH_BOOTSTRAP_NAVIGATE_OPERATION in AUTH_BOOTSTRAP_OPERATIONS


def test_endpoint_absent_from_mcp_tool_catalog() -> None:
    names = set(default_tool_registry().names())
    for name in names:
        assert "bootstrap" not in name
        assert "navigate" not in name
    assert "auth_bootstrap_navigate" not in names
    assert "planner_auth_bootstrap_navigate" not in names


def test_worker_client_has_no_navigation_proxy() -> None:
    attributes = dir(WorkerClient)
    assert not [
        attribute
        for attribute in attributes
        if "navigate" in attribute or "bootstrap" in attribute
    ]
    source = (ROOT / "src" / "planner_mcp" / "worker_client.py").read_text(encoding="utf-8")
    assert NAVIGATE_PATH not in source


def test_no_typed_worker_operation_reaches_navigation() -> None:
    from m365_browser_worker.protocol import WorkerOperation

    for operation in WorkerOperation:
        assert "navigate" not in operation.value
        assert "bootstrap" not in operation.value
    source = (ROOT / "src" / "planner_browser_worker" / "app.py").read_text(encoding="utf-8")
    dispatcher = source.split("async def dispatch_semantic_operation", 1)[1]
    dispatcher = dispatcher.split("@app.post(\"/operations\"", 1)[0]
    assert "auth_bootstrap_navigate" not in dispatcher


def test_control_plane_registration_does_not_expose_navigation() -> None:
    for relative in (
        "src/planner_mcp/registration.py",
        "src/planner_mcp/tools.py",
        "src/m365_mcp/apps/planner/public_surface.py",
    ):
        text = (ROOT / relative).read_text(encoding="utf-8")
        assert "bootstrap_navigate" not in text
        assert NAVIGATE_PATH not in text


# --------------------------------------------------------------------------
# Operator wrapper
# --------------------------------------------------------------------------


def test_operator_wrapper_shape() -> None:
    script = ROOT / "scripts" / "operator_auth_bootstrap_navigate.sh"
    assert script.is_file()
    assert os.access(script, os.X_OK)
    text = script.read_text(encoding="utf-8")
    assert "docker exec" in text
    assert "planner-mcp-browser-worker-1" in text
    assert "127.0.0.1:8090/auth/bootstrap/navigate" in text
    # No URL/host/path argument may be accepted from the operator.
    assert '"$1"' not in text
    assert "$*" not in text
    assert 'if [ "$#" -ne 0 ]' in text


def test_operator_wrapper_rejects_any_argument() -> None:
    script = ROOT / "scripts" / "operator_auth_bootstrap_navigate.sh"
    result = subprocess.run(  # noqa: S603
        ["/bin/bash", str(script), "https://example.com"],  # noqa: S607
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 2
    assert "no arguments" in result.stderr.lower()


def test_runbook_documents_operator_invocation() -> None:
    text = (ROOT / "docs" / "authentication-and-mfa.md").read_text(encoding="utf-8")
    assert "AUTH-094" in text
    assert "scripts/operator_auth_bootstrap_navigate.sh" in text
    assert "docker exec planner-mcp-browser-worker-1" in text
    assert "127.0.0.1:8090/auth/bootstrap/navigate" in text


def test_production_constant_is_safe_default_with_validated_env_override() -> None:
    source = (
        ROOT / "src" / "m365_browser_worker" / "bootstrap_navigation.py"
    ).read_text(encoding="utf-8")
    # The safe default root constant still exists at module level.
    assert 'PLANNER_WEB_BOOTSTRAP_URL = "https://planner.cloud.microsoft/"' in source
    # The override is validated through a closed policy, not accepted blindly.
    assert "validate_planner_web_bootstrap_url" in source
    assert "resolve_planner_web_bootstrap_url" in source
    # A raw env read must be gated by the validator (no unvalidated os.getenv in goto).
    assert "validate_planner_web_bootstrap_url(override).allowed" in source
    # The marketing root is never used as a bare accepted deep link.
    assert "/webui/premiumplan/" in source


def test_browser_config_unchanged_for_navigation() -> None:
    config = BrowserConfig(profile_dir=_UNUSED_PROFILE_DIR, mode="live")
    assert config.is_mock is False


# --------------------------------------------------------------------------
# Real PersistentBrowser navigation path (no Playwright required)
# --------------------------------------------------------------------------


def _real_browser(pages: list[_FakePage]) -> tuple[PersistentBrowser, _FakeContext]:
    browser = PersistentBrowser(
        BrowserConfig(profile_dir=_UNUSED_PROFILE_DIR, mode="live")
    )
    context = _FakeContext(pages)
    browser._context = context  # noqa: SLF001 - injecting a duck-typed context
    browser._playwright = object()  # noqa: SLF001
    return browser, context


async def test_real_browser_navigates_only_to_fixed_target() -> None:
    page = _FakePage("about:blank")
    browser, context = _real_browser([page])
    await browser.navigate_auth_bootstrap()
    assert page.goto_calls == [PLANNER_WEB_BOOTSTRAP_URL]
    assert context.new_page_calls == 0


async def test_real_browser_opens_exactly_one_page_when_none_reusable() -> None:
    existing = _FakePage("https://login.microsoftonline.com/kmsi")
    browser, context = _real_browser([existing])
    await browser.navigate_auth_bootstrap()
    assert existing.goto_calls == []
    assert context.new_page_calls == 1
    assert context.pages[1].goto_calls == [PLANNER_WEB_BOOTSTRAP_URL]


async def test_real_browser_requires_started_context() -> None:
    browser = PersistentBrowser(
        BrowserConfig(profile_dir=_UNUSED_PROFILE_DIR, mode="live")
    )
    with pytest.raises(WorkerUnavailable):
        await browser.navigate_auth_bootstrap()


async def test_real_browser_fails_closed_when_egress_denies(monkeypatch) -> None:
    from m365_browser_worker import browser as browser_module
    from m365_browser_worker.egress import EgressDecision

    page = _FakePage("about:blank")
    browser, context = _real_browser([page])
    monkeypatch.setattr(
        browser_module,
        "evaluate_bootstrap_target",
        lambda: EgressDecision(False, "HOST_NOT_ALLOWLISTED"),
    )
    with pytest.raises(PolicyDenied):
        await browser.navigate_auth_bootstrap()
    assert page.goto_calls == []
    assert context.new_page_calls == 0
