"""Regression tests for GET /auth/bootstrap/collect-observation (AUTH-105).

Verifies the operator-only, loopback, read-only, fixed-scope 4-key
``common.auth`` live attestation observation primitive:

* SOCKET-level loopback admission only (non-loopback -> 404; forwarded headers
  cannot spoof loopback);
* GET only, no query string, no body;
* fixed 4-key scope in fragment order, no caller-supplied selector/stage/url/js;
* produces a complete ``AttestationObservation`` (LIVE_UI, DISCOVERY level,
  binding to the current contract_set_digest) with per-selector result +
  value-free structural_digest only — no DOM/URL/value/credential;
* fails closed (503) when the running context is unusable;
* does NOT add a new POST route (so it cannot mutate M365);
* the produced observation is evaluator-compatible: selector set/order matches the
  fragment and source/level keep evaluation at REVIEW_REQUIRED (no gate weakening).
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path

import httpx
import pytest

from m365_browser_worker.bootstrap_navigation import is_loopback_peer
from m365_browser_worker.collect_observation import (
    COLLECT_OBSERVATION_KEYS,
    COLLECT_OBSERVATION_OPERATION,
    collect_running_observation,
)
from m365_browser_worker.operator_signin import (
    EMAIL_SELECTOR_NAME,
    NEXT_SELECTOR_NAME,
    PASSWORD_SELECTOR_NAME,
    SIGNIN_SELECTOR_NAME,
)
from m365_mcp.attestation import (
    AttestationLevel,
    ObservationSource,
    evaluate_attestation_observation,
    observation_from_dict,
)
from m365_mcp.ui_contract_store import load_ui_contract_set
from planner_browser_worker.app import create_app

COLLECT_PATH = "/auth/bootstrap/collect-observation"

ROOT = Path(__file__).resolve().parent.parent
_AUTH_FRAGMENT = ROOT / "contracts" / "ui_fragments" / "common" / "auth.json"


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
        # Presences of a non-empty url marks the page as "open" for the single
        # page precondition used by the discovery guard's duck-typed double.
        self.url = "https://login.microsoftonline.com/"

    def _resolve(self, strategy: str, value: str, name: str | None) -> _FakeLocator:
        key = (strategy, value, name)
        return _FakeLocator(self._behaviors.get(key, 1))

    def get_by_role(self, role: str, *, name: str | None = None) -> _FakeLocator:
        return self._resolve("role", role, name)

    def get_by_label(self, label: str) -> _FakeLocator:
        return self._resolve("label", label, None)

    def get_by_placeholder(self, placeholder: str) -> _FakeLocator:
        return self._resolve("placeholder", placeholder, None)

    def get_by_test_id(self, test_id: str) -> _FakeLocator:
        return self._resolve("test_id", test_id, None)

    def locator(self, selector: str) -> _FakeLocator:
        return self._resolve("css", selector, None)


class _CollectBrowser:
    """Duck-typed PersistentBrowser exposing the running context for observation."""

    def __init__(
        self,
        *,
        started: bool = True,
        pages: list[_FakePage] | None = None,
        page_behaviors: dict[tuple[str, str, str | None], int] | None = None,
    ) -> None:
        self._started = started
        self._page_behaviors = page_behaviors or {}
        if pages is None:
            pages = [_FakePage(self._page_behaviors)]
        self._context = _FakeContext(pages)

    @property
    def started(self) -> bool:
        return self._started

    # The primitive reads ``_context.pages``; a no-op live guard keeps the app
    # builder contract satisfied for the injected browser.
    def ensure_live_allowed(self, operation: str) -> None:
        return None

    def is_dedicated_persistent_profile(self) -> bool:
        return True

    def auth_origin_approved(self) -> bool:
        return True

    def common_auth_attested(self) -> bool:
        return False


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


def test_collect_observation_scope_is_fixed_four_keys() -> None:
    assert COLLECT_OBSERVATION_KEYS == (
        EMAIL_SELECTOR_NAME,
        NEXT_SELECTOR_NAME,
        PASSWORD_SELECTOR_NAME,
        SIGNIN_SELECTOR_NAME,
    )
    # Operation name must avoid the auth_bootstrap.py grep tokens goto/navigate.
    assert "goto" not in COLLECT_OBSERVATION_OPERATION
    assert "navigate" not in COLLECT_OBSERVATION_OPERATION


def test_is_loopback_peer_socket_level_only() -> None:
    assert is_loopback_peer("127.0.0.1") is True
    assert is_loopback_peer("::1") is True
    assert is_loopback_peer("::ffff:127.0.0.1") is True
    for peer in ("172.18.0.5", "10.0.0.7", "192.168.1.10", "255.255.255.255", "", None):
        assert is_loopback_peer(peer) is False


async def test_loopback_peer_accepted(live_env) -> None:
    browser = _CollectBrowser()
    app = create_app(browser=browser)
    async with _client(app) as client:
        response = await client.get(COLLECT_PATH)
    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    obs = body["observation"]
    assert obs["source"] == "LIVE_UI"
    assert obs["target_level"] == "DISCOVERY"
    keys = [item["selector_key"] for item in obs["selector_observations"]]
    assert keys == list(COLLECT_OBSERVATION_KEYS)


async def test_docker_network_peer_denied(live_env) -> None:
    browser = _CollectBrowser()
    app = create_app(browser=browser)
    async with _client(app, peer=("172.18.0.5", 5555)) as client:
        response = await client.get(COLLECT_PATH)
    assert response.status_code == 404


async def test_forwarded_headers_cannot_spoof_loopback(live_env) -> None:
    browser = _CollectBrowser()
    app = create_app(browser=browser)
    spoofs = (
        {"X-Forwarded-For": "127.0.0.1"},
        {"X-Forwarded-For": "127.0.0.1, 172.18.0.5"},
        {"X-Real-IP": "127.0.0.1"},
        {"Forwarded": 'for="127.0.0.1"'},
    )
    async with _client(app, peer=("172.18.0.9", 6666)) as client:
        for headers in spoofs:
            response = await client.get(COLLECT_PATH, headers=headers)
            assert response.status_code == 404


async def test_query_string_rejected(live_env) -> None:
    browser = _CollectBrowser()
    app = create_app(browser=browser)
    async with _client(app) as client:
        for query in ("?url=https://example.com", "?x=1", "?selector=auth.login_email_input"):
            response = await client.get(f"{COLLECT_PATH}{query}")
            assert response.status_code == 400
            assert response.json()["detail"]["error"] == "INVALID_REQUEST"


async def test_post_method_not_allowed(live_env) -> None:
    browser = _CollectBrowser()
    app = create_app(browser=browser)
    async with _client(app) as client:
        response = await client.post(COLLECT_PATH, json={"selector": "x"})
    # GET-only: POST is not registered for this path.
    assert response.status_code == 405


async def test_unstarted_browser_fails_closed(live_env) -> None:
    browser = _CollectBrowser(started=False)
    app = create_app(browser=browser)
    async with _client(app) as client:
        response = await client.get(COLLECT_PATH)
    assert response.status_code == 503
    assert response.json()["detail"]["error"] == "OBSERVATION_FAILED"


async def test_no_new_post_route_registered() -> None:
    app = create_app()
    collect_posts = {
        getattr(route, "path", "")
        for route in app.routes
        if "POST" in (getattr(route, "methods", set()) or set())
        and getattr(route, "path", "").endswith("collect-observation")
    }
    assert not collect_posts


async def test_produced_observation_evaluator_compatible(live_env) -> None:
    """A 4-key UNIQUE_MATCH observation is structurally valid and stays REVIEW_REQUIRED.

    It must NOT weaken the fail-closed evaluator: the observation binds to the
    current contract_set_digest and matches the fragment selector set/order, but
    because it is DISCOVERY/LIVE_UI it can only yield REVIEW_REQUIRED — never
    PASSED. Promotion stays PR/evidence based.
    """
    browser = _CollectBrowser()
    app = create_app(browser=browser)
    async with _client(app) as client:
        response = await client.get(COLLECT_PATH)
    assert response.status_code == 200
    obs = observation_from_dict(response.json()["observation"])

    contract_set = load_ui_contract_set()
    decision = evaluate_attestation_observation(contract_set, obs)

    # Binding is valid (no SELECTOR_SET_OR_ORDER_MISMATCH / digest mismatch).
    assert decision.state.value == "REVIEW_REQUIRED"
    assert "SELECTOR_SET_OR_ORDER_MISMATCH" not in decision.reasons
    assert "CONTRACT_SET_DIGEST_MISMATCH" not in decision.reasons
    # No gate weakening: never PASSED from a DISCOVERY observation.
    assert decision.state.value != "PASSED"


async def test_collect_running_observation_yields_complete_observation() -> None:
    browser = _CollectBrowser()
    observation = await collect_running_observation(browser, fragment_id="common.auth")
    assert observation.source is ObservationSource.LIVE_UI
    assert observation.target_level is AttestationLevel.DISCOVERY
    assert len(observation.selector_observations) == 4
    assert tuple(o.selector_key for o in observation.selector_observations) == (
        EMAIL_SELECTOR_NAME,
        NEXT_SELECTOR_NAME,
        PASSWORD_SELECTOR_NAME,
        SIGNIN_SELECTOR_NAME,
    )
    # No DOM/URL/value/credential ever leaves: only result + structural_digest.
    for sel in observation.selector_observations:
        assert sel.result.value in {"NO_MATCH", "UNIQUE_MATCH", "AMBIGUOUS"}
        if sel.result.value == "UNIQUE_MATCH":
            assert sel.structural_digest is not None
            assert sel.structural_digest.startswith("sha256:")
        else:
            assert sel.structural_digest is None
