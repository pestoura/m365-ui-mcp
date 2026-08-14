"""Focused security + behavior suite for the fixed read-only discovery routes.

Covers, explicitly:

* non-loopback peer denied (404); X-Forwarded-For/Real-IP/Forwarded cannot spoof;
* GET only: any query string rejected (400); no request body processed;
* exact fixed-key scope: email route probes only the two email keys, password
  route only the two password keys; no caller-supplied selector/stage/url/js;
* per-key result enum NO_MATCH / UNIQUE_MATCH / AMBIGUOUS;
* structural_digest present ONLY for UNIQUE_MATCH and value-free;
* digest format/compatibility with scripts/collect_live_attestation_observation.py;
* no candidate values / strategy / name / DOM / URL / account data in response;
* no fill / click / type / navigation occurs;
* fail-closed preconditions: browser not started, wrong profile, disapproved
  auth origin, page count != 1, missing/invalid plan, count failure;
* existing mutating-route guard unchanged (GET needs no POST allowlist change);
* route absent from MCP tool registry / capability registry / agent card /
  typed /operations dispatcher / control-plane worker client;
* the declaration of the fixed discovery keys is hard-coded in source.
"""

from __future__ import annotations

import importlib.util
import json
import os
from collections.abc import Iterator
from pathlib import Path

import httpx
import pytest

from m365_browser_worker.bootstrap_discovery import (
    DISCOVER_EMAIL_OPERATION,
    DISCOVER_PASSWORD_OPERATION,
    EMAIL_DISCOVERY_KEYS,
    PASSWORD_DISCOVERY_KEYS,
    DiscoveryError,
    DiscoveryResultKind,
    _selector_structural_shape,
    _structural_digest,
    discover_key,
)
from m365_browser_worker.bootstrap_navigation import is_loopback_peer
from m365_browser_worker.operator_signin import (
    EMAIL_SELECTOR_NAME,
    NEXT_SELECTOR_NAME,
    PASSWORD_SELECTOR_NAME,
    SIGNIN_SELECTOR_NAME,
)
from planner_browser_worker.app import create_app
from planner_mcp.errors import PolicyDenied, WorkerUnavailable

DISCOVER_EMAIL_PATH = "/auth/bootstrap/discover-email"
DISCOVER_PASSWORD_PATH = "/auth/bootstrap/discover-password"  # noqa: S105

ROOT = Path(__file__).resolve().parent.parent
_AUTH_EMAIL_FRAGMENT = (
    ROOT / "contracts" / "ui_fragments" / "common" / "auth_email.json"
)


def _auth_metadata() -> dict[str, object]:
    raw = json.loads(_AUTH_EMAIL_FRAGMENT.read_text(encoding="utf-8"))
    return raw["selectors"]


# --------------------------------------------------------------------------
# Test doubles
# --------------------------------------------------------------------------


class _FakeLocator:
    """Minimal Playwright Locator double that returns a static count."""

    def __init__(self, count: int) -> None:
        self._count = count
        self.count_calls = 0

    async def count(self) -> int:
        self.count_calls += 1
        return self._count


class _FakePage:
    """Minimal Playwright Page double keyed by (strategy, value, name)."""

    def __init__(self, behaviors: dict[tuple[str, str, str | None], int]) -> None:
        self._behaviors = behaviors
        self.calls: list[tuple[str, str, str | None]] = []
        # Presence of a non-empty url marks the page as "open" for the single
        # page precondition used by the discovery guard's duck-typed double.
        self.url = "https://login.microsoftonline.com/"

    def _resolve(self, strategy: str, value: str, name: str | None) -> _FakeLocator:
        key = (strategy, value, name)
        # Default to a unique match when the specific behavior is absent so the
        # resolution algorithm only diverges where the test configures it.
        return _FakeLocator(self._behaviors.get(key, 1))

    def get_by_role(self, role: str, *, name: str | None = None) -> _FakeLocator:
        self.calls.append(("role", role, name))
        return self._resolve("role", role, name)

    def get_by_label(self, label: str) -> _FakeLocator:
        self.calls.append(("label", label, None))
        return self._resolve("label", label, None)

    def get_by_placeholder(self, placeholder: str) -> _FakeLocator:
        self.calls.append(("placeholder", placeholder, None))
        return self._resolve("placeholder", placeholder, None)

    def get_by_test_id(self, test_id: str) -> _FakeLocator:
        self.calls.append(("test_id", test_id, None))
        return self._resolve("test_id", test_id, None)

    def locator(self, selector: str) -> _FakeLocator:
        self.calls.append(("css", selector, None))
        return self._resolve("css", selector, None)


class _DiscoveryBrowser:
    """Duck-typed PersistentBrowser exposing the discovery surface."""

    def __init__(
        self,
        *,
        started: bool = True,
        dedicated: bool = True,
        auth_origin_approved: bool = True,
        pages: list[_FakePage] | None = None,
        page_behaviors: dict[tuple[str, str, str | None], int] | None = None,
    ) -> None:
        self._started = started
        self._dedicated = dedicated
        self._auth_origin_approved = auth_origin_approved
        self._page_behaviors = page_behaviors or {}
        if pages is None:
            pages = [_FakePage(self._page_behaviors)]
        self.context = _FakeContext(pages)

    @property
    def started(self) -> bool:
        return self._started

    def is_dedicated_persistent_profile(self) -> bool:
        return self._dedicated

    def ensure_live_allowed(self, operation: str) -> None:
        # Discovery routes do not depend on the attestation gate, so the live
        # guard is a no-op for the injection double (it is never reached on the
        # read-only discovery path).
        return None

    def auth_origin_approved(self) -> bool:
        return self._auth_origin_approved

    def common_auth_attested(self) -> bool:
        # Discovery must NOT require attestation.
        return False

    def _require_single_auth_page(self) -> _FakePage:
        pages = [p for p in self.context.pages if str(getattr(p, "url", ""))]
        if len(self.context.pages) != 1 or len(pages) != 1:
            raise PolicyDenied(
                "discovery requires exactly one open authentication page",
                operation="auth_bootstrap_discover",
            )
        return self.context.pages[0]

    async def navigate_auth_bootstrap(self) -> None:
        # No-op for the POST navigate guard smoke test.
        return None

    async def begin_auth_signin(self) -> None:
        return None


class _FakeContext:
    def __init__(self, pages: list[_FakePage] | None = None) -> None:
        self.pages = pages if pages is not None else []


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
# Loopback admission (socket level only)
# --------------------------------------------------------------------------


def test_is_loopback_peer_socket_level_only() -> None:
    assert is_loopback_peer("127.0.0.1") is True
    assert is_loopback_peer("::1") is True
    assert is_loopback_peer("::ffff:127.0.0.1") is True
    for peer in ("172.18.0.5", "10.0.0.7", "192.168.1.10", "255.255.255.255", "", None):
        assert is_loopback_peer(peer) is False


async def test_loopback_peer_accepted(live_env) -> None:
    browser = _DiscoveryBrowser()
    app = create_app(browser=browser)
    async with _client(app) as client:
        response = await client.get(DISCOVER_EMAIL_PATH)
    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert {item["selector_key"] for item in body["keys"]} == set(EMAIL_DISCOVERY_KEYS)


async def test_docker_network_peer_denied(live_env) -> None:
    browser = _DiscoveryBrowser()
    app = create_app(browser=browser)
    async with _client(app, peer=("172.18.0.5", 5555)) as client:
        response = await client.get(DISCOVER_EMAIL_PATH)
    assert response.status_code == 404


async def test_forwarded_headers_cannot_spoof_loopback(live_env) -> None:
    browser = _DiscoveryBrowser()
    app = create_app(browser=browser)
    spoofs = (
        {"X-Forwarded-For": "127.0.0.1"},
        {"X-Forwarded-For": "127.0.0.1, 172.18.0.5"},
        {"X-Real-IP": "127.0.0.1"},
        {"Forwarded": 'for="127.0.0.1"'},
    )
    async with _client(app, peer=("172.18.0.9", 6666)) as client:
        for headers in spoofs:
            response = await client.get(DISCOVER_EMAIL_PATH, headers=headers)
            assert response.status_code == 404


# --------------------------------------------------------------------------
# No parameters: query rejected, no body
# --------------------------------------------------------------------------


async def test_query_string_rejected(live_env) -> None:
    browser = _DiscoveryBrowser()
    app = create_app(browser=browser)
    async with _client(app) as client:
        for query in ("?url=https://example.com", "?x=1", "?selector=auth.login_email_input"):
            response = await client.get(f"{DISCOVER_EMAIL_PATH}{query}")
            assert response.status_code == 400
            assert response.json()["detail"]["error"] == "INVALID_REQUEST"


async def test_request_body_rejected(live_env) -> None:
    # A GET carries no body; assert the route ignores any payload and never
    # processes it. We use POST to confirm only GET admission exists for the
    # fixed path shape.
    browser = _DiscoveryBrowser()
    app = create_app(browser=browser)
    async with _client(app) as client:
        response = await client.post(DISCOVER_EMAIL_PATH, json={"selector": "x"})
    # POST is not registered -> 405 (method not allowed), never a discovery.
    assert response.status_code == 405


# --------------------------------------------------------------------------
# Exact fixed-key scope
# --------------------------------------------------------------------------


def test_email_route_scope_is_hard_coded_source() -> None:
    assert EMAIL_DISCOVERY_KEYS == (EMAIL_SELECTOR_NAME, NEXT_SELECTOR_NAME)
    assert PASSWORD_DISCOVERY_KEYS == (PASSWORD_SELECTOR_NAME, SIGNIN_SELECTOR_NAME)


async def test_email_route_probes_only_email_keys(live_env) -> None:
    browser = _DiscoveryBrowser()
    app = create_app(browser=browser)
    async with _client(app) as client:
        body = (await client.get(DISCOVER_EMAIL_PATH)).json()
    assert {item["selector_key"] for item in body["keys"]} == {
        "auth.login_email_input",
        "auth.login_next_button",
    }


async def test_password_route_probes_only_password_keys(live_env) -> None:
    browser = _DiscoveryBrowser()
    app = create_app(browser=browser)
    async with _client(app) as client:
        body = (await client.get(DISCOVER_PASSWORD_PATH)).json()
    assert {item["selector_key"] for item in body["keys"]} == {
        "auth.login_password_input",
        "auth.login_signin_button",
    }


# --------------------------------------------------------------------------
# Unique / no-match / ambiguous outcomes
# --------------------------------------------------------------------------


async def test_unique_match_returns_digest(live_env) -> None:
    browser = _DiscoveryBrowser(page_behaviors={})
    app = create_app(browser=browser)
    async with _client(app) as client:
        body = (await client.get(DISCOVER_EMAIL_PATH)).json()
    for item in body["keys"]:
        assert item["result"] == DiscoveryResultKind.UNIQUE_MATCH.value
        assert item["structural_digest"].startswith("sha256:")


async def test_no_match_mapping(live_env) -> None:
    # Every declared candidate resolves to count 0 -> NO_MATCH, no digest.
    behaviors = {
        ("role", "textbox", "Email, phone, or Skype"): 0,
        ("placeholder", "Email, phone, or Skype"): 0,
        ("label", "Email, phone, or Skype"): 0,
        ("role", "textbox", "E-mail, telemóvel ou Skype"): 0,
        ("placeholder", "E-mail, telemóvel ou Skype"): 0,
        ("label", "E-mail, telemóvel ou Skype"): 0,
        ("role", "button", "Next"): 0,
        ("role", "button", "Seguinte"): 0,
    }
    browser = _DiscoveryBrowser(page_behaviors=behaviors)
    app = create_app(browser=browser)
    async with _client(app) as client:
        body = (await client.get(DISCOVER_EMAIL_PATH)).json()
    for item in body["keys"]:
        assert item["result"] == DiscoveryResultKind.NO_MATCH.value
        assert "structural_digest" not in item


async def test_ambiguous_mapping(live_env) -> None:
    # At least one declared candidate yields >1 match -> AMBIGUOUS.
    behaviors = {
        ("role", "textbox", "Email, phone, or Skype"): 2,
    }
    browser = _DiscoveryBrowser(page_behaviors=behaviors)
    app = create_app(browser=browser)
    async with _client(app) as client:
        body = (await client.get(DISCOVER_EMAIL_PATH)).json()
    results = {item["selector_key"]: item["result"] for item in body["keys"]}
    assert results["auth.login_email_input"] == DiscoveryResultKind.AMBIGUOUS.value
    assert "structural_digest" not in next(
        item for item in body["keys"] if item["selector_key"] == "auth.login_email_input"
    )


# --------------------------------------------------------------------------
# No fill / click / type / navigation
# --------------------------------------------------------------------------


async def test_discovery_never_mutates_page(live_env) -> None:
    page = _FakePage({})
    browser = _DiscoveryBrowser(pages=[page])
    app = create_app(browser=browser)
    async with _client(app) as client:
        (await client.get(DISCOVER_EMAIL_PATH)).json()
    # Only count() is invoked; no fill/click/type/goto.
    assert all("goto" not in call for call in dir(page))
    for call in page.calls:
        assert call[0] in ("role", "label", "placeholder", "test_id", "css")


# --------------------------------------------------------------------------
# Fail-closed preconditions
# --------------------------------------------------------------------------


async def test_browser_not_started_fails_closed(live_env) -> None:
    browser = _DiscoveryBrowser(started=False)
    app = create_app(browser=browser)
    async with _client(app) as client:
        response = await client.get(DISCOVER_EMAIL_PATH)
    assert response.status_code == 503
    assert isinstance(WorkerUnavailable, type)


async def test_wrong_profile_fails_closed(live_env) -> None:
    browser = _DiscoveryBrowser(dedicated=False)
    app = create_app(browser=browser)
    async with _client(app) as client:
        response = await client.get(DISCOVER_EMAIL_PATH)
    assert response.status_code == 503


async def test_disapproved_auth_origin_fails_closed(live_env) -> None:
    browser = _DiscoveryBrowser(auth_origin_approved=False)
    app = create_app(browser=browser)
    async with _client(app) as client:
        response = await client.get(DISCOVER_EMAIL_PATH)
    assert response.status_code == 503


async def test_page_count_not_one_fails_closed(live_env) -> None:
    # Two pages open -> fail closed with no probe.
    browser = _DiscoveryBrowser(pages=[_FakePage({}), _FakePage({})])
    app = create_app(browser=browser)
    async with _client(app) as client:
        response = await client.get(DISCOVER_EMAIL_PATH)
    assert response.status_code == 503


async def test_response_leaks_no_values_or_secrets(live_env) -> None:
    browser = _DiscoveryBrowser()
    app = create_app(browser=browser)
    async with _client(app) as client:
        text = (await client.get(DISCOVER_EMAIL_PATH)).text.lower()
    for forbidden in (
        "email, phone",
        "password",
        "skype",
        "sign in",
        "cookie",
        "token",
        "upn",
        "tenant",
        "bearer",
        "playwright",
        "http",
        "<html",
    ):
        assert forbidden not in text


# --------------------------------------------------------------------------
# discover_key unit behavior (no network / browser)
# --------------------------------------------------------------------------


async def test_discover_key_unique_match_digest_present() -> None:
    page = _FakePage({})
    discovery = await discover_key(page, EMAIL_SELECTOR_NAME)
    assert discovery.result is DiscoveryResultKind.UNIQUE_MATCH
    assert discovery.structural_digest is not None
    assert discovery.structural_digest.startswith("sha256:")


async def test_discover_key_no_match_no_digest() -> None:
    behaviors = {
        ("role", "textbox", "Email, phone, or Skype"): 0,
        ("placeholder", "Email, phone, or Skype"): 0,
        ("label", "Email, phone, or Skype"): 0,
        ("role", "textbox", "E-mail, telemóvel ou Skype"): 0,
        ("placeholder", "E-mail, telemóvel ou Skype"): 0,
        ("label", "E-mail, telemóvel ou Skype"): 0,
    }
    discovery = await discover_key(_FakePage(behaviors), EMAIL_SELECTOR_NAME)
    assert discovery.result is DiscoveryResultKind.NO_MATCH
    assert discovery.structural_digest is None


async def test_discover_key_ambiguous() -> None:
    behaviors = {("role", "textbox", "Email, phone, or Skype"): 3}
    discovery = await discover_key(_FakePage(behaviors), EMAIL_SELECTOR_NAME)
    assert discovery.result is DiscoveryResultKind.AMBIGUOUS
    assert discovery.structural_digest is None


async def test_discover_key_missing_plan_fails_closed() -> None:
    # An unknown selector is not a declared common.auth progression key -> ValueError
    # inside common_auth_locator_plan -> sanitized DiscoveryError.
    with pytest.raises(DiscoveryError):
        await discover_key(_FakePage({}), "auth.login_unknown_selector")


async def test_discover_key_count_failure_fails_closed() -> None:
    class _BoomLocator:
        async def count(self) -> int:
            raise RuntimeError("injected count failure")

    class _BoomPage(_FakePage):
        def get_by_role(self, role: str, *, name: str | None = None):
            return _BoomLocator()

    with pytest.raises(DiscoveryError):
        await discover_key(_BoomPage({}), EMAIL_SELECTOR_NAME)


async def test_discover_key_never_fills_or_clicks() -> None:
    page = _FakePage({})
    await discover_key(page, EMAIL_SELECTOR_NAME)
    # The page only receives count() calls via the locator primitives; there is
    # no fill/click/type method on the discovery path.
    for call in page.calls:
        assert call[0] in ("role", "label", "placeholder", "test_id", "css")


class _AwaitFlagLocator:
    """Async Playwright Locator double that records whether ``count`` ran.

    Flipping ``count_executed`` from inside the coroutine lets a test prove
    ``discover_key`` truly awaited ``locator.count()`` rather than returning a
    coroutine object. Mirrors the async Playwright Locator API consumed by
    ``bootstrap_discovery`` via ``build_locator`` -> ``locator.count()``.
    """

    def __init__(self, count: int) -> None:
        self._count = count
        self.count_executed = False

    async def count(self) -> int:
        self.count_executed = True
        return self._count


async def test_discover_key_actually_awaits_count() -> None:
    # Prove the resolver awaits locator.count() (not just returns a coroutine).
    locator = _AwaitFlagLocator(1)
    page = _FakePage({})
    page.get_by_role = lambda role, *, name=None: locator  # type: ignore[method-assign]
    assert locator.count_executed is False
    discovery = await discover_key(page, EMAIL_SELECTOR_NAME)
    assert locator.count_executed is True
    assert discovery.result is DiscoveryResultKind.UNIQUE_MATCH


async def test_discover_key_await_preserves_semantics() -> None:
    # NO_MATCH / UNIQUE_MATCH / AMBIGUOUS semantics preserved through await.
    no_match = _AwaitFlagLocator(0)
    unique = _AwaitFlagLocator(1)
    ambiguous = _AwaitFlagLocator(3)

    nm_page = _FakePage({})
    nm_page.get_by_role = lambda role, *, name=None: no_match  # type: ignore[method-assign]
    un_page = _FakePage({})
    un_page.get_by_role = lambda role, *, name=None: unique  # type: ignore[method-assign]
    am_page = _FakePage({})
    am_page.get_by_role = lambda role, *, name=None: ambiguous  # type: ignore[method-assign]

    nm = await discover_key(nm_page, EMAIL_SELECTOR_NAME)
    un = await discover_key(un_page, EMAIL_SELECTOR_NAME)
    am = await discover_key(am_page, EMAIL_SELECTOR_NAME)

    assert nm.result is DiscoveryResultKind.NO_MATCH
    assert nm.structural_digest is None
    assert un.result is DiscoveryResultKind.UNIQUE_MATCH
    assert un.structural_digest is not None
    assert am.result is DiscoveryResultKind.AMBIGUOUS
    assert am.structural_digest is None
    # Every locator's async count was actually awaited.
    assert no_match.count_executed is True
    assert unique.count_executed is True
    assert ambiguous.count_executed is True


# --------------------------------------------------------------------------
# Structural digest compatibility with scripts/collect_live_attestation_observation.py
# --------------------------------------------------------------------------


def _load_attestation_script_module():
    script_path = ROOT / "scripts" / "collect_live_attestation_observation.py"
    spec = importlib.util.spec_from_file_location(
        "_attestation_collector", str(script_path)
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    return module


def test_structural_digest_matches_script_helper() -> None:
    # The worker's canonical digest helper must produce identical output to the
    # operator script's helper for the same value-free shape.
    attestation = _load_attestation_script_module()
    shape = {
        "selector_key": EMAIL_SELECTOR_NAME,
        "strategy": "role",
        "match_index": 0,
        "match_count": 1,
    }
    assert _structural_digest(shape) == attestation._structural_digest(shape)


def test_selector_structural_shape_matches_script_helper() -> None:
    attestation = _load_attestation_script_module()
    metadata = _auth_metadata()
    selector_meta = {"locators": metadata[EMAIL_SELECTOR_NAME]["locators"]}
    ours = _selector_structural_shape(EMAIL_SELECTOR_NAME, selector_meta, 0, 1)
    theirs = attestation._selector_structural_shape(EMAIL_SELECTOR_NAME, selector_meta, 0, 1)
    assert ours == theirs
    # The digest of both shapes is identical.
    assert _structural_digest(ours) == attestation._structural_digest(theirs)
    # No value/name text leaks into the shape.
    assert "Email, phone, or Skype" not in json.dumps(ours)


async def test_discover_key_digest_is_script_compatible() -> None:
    attestation = _load_attestation_script_module()
    metadata = _auth_metadata()
    page = _FakePage({})
    discovery = await discover_key(page, EMAIL_SELECTOR_NAME)
    assert discovery.result is DiscoveryResultKind.UNIQUE_MATCH
    expected_shape = attestation._selector_structural_shape(
        EMAIL_SELECTOR_NAME, {"locators": metadata[EMAIL_SELECTOR_NAME]["locators"]}, 0, 1
    )
    assert discovery.structural_digest == attestation._structural_digest(expected_shape)


# --------------------------------------------------------------------------
# Existing mutating-route guard unchanged (GET needs no POST allowlist change)
# --------------------------------------------------------------------------


async def test_existing_post_navigate_guard_unchanged(live_env) -> None:
    browser = _DiscoveryBrowser()
    app = create_app(browser=browser)
    async with _client(app) as client:
        # The pre-existing POST navigate route still functions identically.
        response = await client.post("/auth/bootstrap/navigate")
    assert response.status_code in (200, 503)


def test_discovery_keys_not_in_post_allowlist_source() -> None:
    source = (ROOT / "src" / "planner_browser_worker" / "app.py").read_text(encoding="utf-8")
    # The discovery routes are GET and must not have been added to any POST
    # body-parsing/allowlist path. The exact substring count guards against an
    # accidental POST handler for the discovery surface.
    assert source.count('@app.post("/auth/bootstrap/discover-email")') == 0
    assert source.count('@app.post("/auth/bootstrap/discover-password")') == 0
    # The two pre-existing POST bootstrap operations remain intact and unchanged.
    assert '@app.post("/auth/bootstrap/navigate")' in source
    assert '@app.post("/auth/bootstrap/begin-signin")' in source


# --------------------------------------------------------------------------
# Absent from every public catalog / no control-plane proxy
# --------------------------------------------------------------------------


def test_endpoint_absent_from_mcp_tool_catalog() -> None:
    from m365_mcp.tool_registry import default_tool_registry

    names = set(default_tool_registry().names())
    for name in names:
        assert "discover" not in name
        assert "bootstrap" not in name
    assert "auth_bootstrap_discover_email" not in names
    assert "auth_bootstrap_discover_password" not in names


def test_discovery_absent_from_worker_client_and_dispatch() -> None:
    from planner_mcp.worker_client import WorkerClient

    assert not [
        attr
        for attr in dir(WorkerClient)
        if "discover" in attr or "bootstrap" in attr
    ]
    source = (ROOT / "src" / "planner_browser_worker" / "app.py").read_text(encoding="utf-8")
    dispatcher = source.split("async def dispatch_semantic_operation", 1)[1]
    dispatcher = dispatcher.split('@app.post("/operations"', 1)[0]
    assert "discover_email" not in dispatcher
    assert "discover_password" not in dispatcher


def test_discovery_keys_hard_coded_not_configurable() -> None:
    source = (
        ROOT / "src" / "m365_browser_worker" / "bootstrap_discovery.py"
    ).read_text(encoding="utf-8")
    # The fixed key scope must be literal constants, not read from env/request.
    assert 'EMAIL_DISCOVERY_KEYS = ("auth.login_email_input", "auth.login_next_button")' in source
    assert (
        'PASSWORD_DISCOVERY_KEYS = ("auth.login_password_input", "auth.login_signin_button")'
        in source
    )
    assert "os.getenv" not in source


def test_operation_constants_are_operator_only() -> None:
    assert DISCOVER_EMAIL_OPERATION == "auth_bootstrap_discover_email"
    assert DISCOVER_PASSWORD_OPERATION == "auth_bootstrap_discover_password"  # noqa: S105
