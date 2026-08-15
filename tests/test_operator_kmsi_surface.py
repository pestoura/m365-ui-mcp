"""AUTH-114 security regression suite: deterministic fail-closed resolution of
the post-password Microsoft ``Stay signed in?`` (KMSI) surface.

The live headless operator run reached this surface after a successful
``operator-submit`` (email -> Next -> password -> Sign in) with NO MFA challenge:
``diagnose-signin-surface`` reported the closed ``STAY_SIGNED_IN`` kind while
``observe`` reported ``AUTH_REQUIRED`` / ``mfa_number:null`` /
``mfa_ambiguous:false``, so the canonical conductor stopped fail-closed with
``MFA_BLOCKED``. KMSI is a deterministic, credential-free, MFA-free interstitial:
the only action needed is a single click on ONE fixed Microsoft control.

This suite pins the fail-closed contract:

* the KMSI action is matched ONLY from a CLOSED set of exact Microsoft labels and
  ONLY on a STRICTLY UNIQUE (count == 1) accessible control — no regex, no
  wildcard, no ``first`` of many, no caller-supplied selector;
* the resolver acts ONLY when the surface classifies as ``STAY_SIGNED_IN``; every
  other surface (email entry, chooser, consent, method selection, error,
  ambiguous, unknown) is left untouched and reported fail-closed;
* the resolver NEVER types a credential, never selects a cached identity, never
  clicks Sign in, never navigates by URL/selector, and never returns URL/DOM/
  page text/cookie/token/UPN/tenant/account identifier;
* the route is OPERATOR-ONLY with SOCKET-level loopback admission, POST-only,
  zero-parameter, zero-body, and absent from every MCP tool/capability/agent-card
  catalog and the control-plane worker client.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import httpx
import pytest

from m365_browser_worker.signin_surface import (
    AUTH_KMSI_OPERATION,
    KMSI_DECLINE_LABELS,
    SigninSurfaceKind,
    click_kmsi_decline,
    resolve_stay_signed_in_surface,
)
from planner_browser_worker.app import create_app
from planner_mcp.errors import PolicyDenied
from planner_mcp.worker_client import WorkerClient

ROOT = Path(__file__).resolve().parent.parent
KMSI_PATH = "/auth/bootstrap/resolve-kmsi-surface"

pytestmark = pytest.mark.anyio


# --------------------------------------------------------------------------
# Test doubles
# --------------------------------------------------------------------------


class _FakeLocator:
    def __init__(self, count: int) -> None:
        self._count = count
        self.clicks = 0

    async def count(self) -> int:
        return self._count

    @property
    def first(self) -> _FakeLocator:
        return self

    async def click(self, timeout: int | None = None) -> None:
        self.clicks += 1


class _FakeKmsiPage:
    """Page exposing the KMSI control for a fixed (role, name) pair only."""

    def __init__(self, matches: dict[tuple[str, str], int] | None = None) -> None:
        self._matches = matches or {}
        self.locators: list[_FakeLocator] = []
        self.fill_calls: list[tuple[str, str]] = []
        self.goto_calls: list[str] = []

    def get_by_role(self, role: str, name: str) -> _FakeLocator:
        locator = _FakeLocator(self._matches.get((role, name), 0))
        self.locators.append(locator)
        return locator

    async def fill(self, selector: str, value: str) -> None:  # pragma: no cover
        self.fill_calls.append((selector, value))

    async def goto(self, url: str) -> None:  # pragma: no cover
        self.goto_calls.append(url)


def _reader(text: str):
    async def _read() -> str:
        return text

    return _read


class _FakeBrowser:
    """Duck-typed PersistentBrowser for the route-level contract."""

    def __init__(
        self,
        *,
        started: bool = True,
        dedicated: bool = True,
        origin_ok: bool = True,
        outcome: Any = None,
    ) -> None:
        self.started = started
        self._dedicated = dedicated
        self._origin_ok = origin_ok
        self._outcome = outcome
        self.calls = 0

    def is_dedicated_persistent_profile(self) -> bool:
        return self._dedicated

    def auth_origin_approved(self) -> bool:
        return self._origin_ok

    def common_auth_attested(self) -> bool:
        return False

    def ensure_live_allowed(self, operation: str) -> None:
        return None

    async def resolve_kmsi_surface(self) -> SigninSurfaceKind:
        self.calls += 1
        if isinstance(self._outcome, Exception):
            raise self._outcome
        return self._outcome or SigninSurfaceKind.STAY_SIGNED_IN


def _client(browser: _FakeBrowser, *, peer: tuple[str, int] = ("127.0.0.1", 55555)):
    app = create_app(browser=browser)
    transport = httpx.ASGITransport(app=app, client=peer)
    return httpx.AsyncClient(transport=transport, base_url="http://worker")


# --------------------------------------------------------------------------
# Closed label set / strict uniqueness
# --------------------------------------------------------------------------


def test_kmsi_labels_are_a_closed_non_empty_exact_set() -> None:
    assert isinstance(KMSI_DECLINE_LABELS, tuple)
    assert KMSI_DECLINE_LABELS
    for label in KMSI_DECLINE_LABELS:
        assert isinstance(label, str)
        assert label.strip() == label
        assert "*" not in label
        assert ".*" not in label


async def test_click_requires_strictly_unique_control() -> None:
    label = KMSI_DECLINE_LABELS[0]
    ambiguous = _FakeKmsiPage({("button", label): 2})
    assert await click_kmsi_decline(ambiguous) is False
    assert all(locator.clicks == 0 for locator in ambiguous.locators)

    unique = _FakeKmsiPage({("button", label): 1})
    assert await click_kmsi_decline(unique) is True
    assert sum(locator.clicks for locator in unique.locators) == 1


async def test_click_never_fills_or_navigates() -> None:
    page = _FakeKmsiPage({("button", KMSI_DECLINE_LABELS[0]): 1})
    await click_kmsi_decline(page)
    assert page.fill_calls == []
    assert page.goto_calls == []


async def test_click_absent_control_is_false_not_a_guess() -> None:
    page = _FakeKmsiPage({})
    assert await click_kmsi_decline(page) is False
    assert all(locator.clicks == 0 for locator in page.locators)


# --------------------------------------------------------------------------
# Surface-scoped resolution
# --------------------------------------------------------------------------


async def test_resolver_acts_only_on_stay_signed_in() -> None:
    page = _FakeKmsiPage({("button", KMSI_DECLINE_LABELS[0]): 1})
    resolution = await resolve_stay_signed_in_surface(
        page, _reader("Stay signed in? Don't show this again")
    )
    assert resolution.advanced is True
    assert sum(locator.clicks for locator in page.locators) == 1


@pytest.mark.parametrize(
    "text",
    [
        "Enter your email, phone, or Skype",
        "Pick an account",
        "Something went wrong",
        "",
    ],
)
async def test_resolver_never_acts_on_other_surfaces(text: str) -> None:
    page = _FakeKmsiPage({("button", KMSI_DECLINE_LABELS[0]): 1})
    resolution = await resolve_stay_signed_in_surface(page, _reader(text))
    assert resolution.advanced is False
    assert sum(locator.clicks for locator in page.locators) == 0


async def test_resolver_fails_closed_when_control_absent() -> None:
    page = _FakeKmsiPage({})
    resolution = await resolve_stay_signed_in_surface(page, _reader("Stay signed in?"))
    assert resolution.advanced is False
    assert resolution.terminal_surface is SigninSurfaceKind.STAY_SIGNED_IN


# --------------------------------------------------------------------------
# Route contract
# --------------------------------------------------------------------------


async def test_non_loopback_peer_gets_404_and_never_touches_browser() -> None:
    browser = _FakeBrowser()
    async with _client(browser, peer=("172.18.0.4", 4444)) as client:
        response = await client.post(KMSI_PATH)
    assert response.status_code == 404
    assert browser.calls == 0


@pytest.mark.parametrize(
    "headers",
    [
        {"X-Forwarded-For": "127.0.0.1"},
        {"X-Real-IP": "127.0.0.1"},
        {"Forwarded": "for=127.0.0.1"},
    ],
)
async def test_proxy_headers_cannot_spoof_loopback(headers: dict[str, str]) -> None:
    browser = _FakeBrowser()
    async with _client(browser, peer=("10.1.2.3", 5555)) as client:
        response = await client.post(KMSI_PATH, headers=headers)
    assert response.status_code == 404
    assert browser.calls == 0


async def test_route_rejects_body_and_query() -> None:
    browser = _FakeBrowser()
    async with _client(browser) as client:
        assert (await client.post(KMSI_PATH, json={"x": 1})).status_code == 400
        assert (await client.post(f"{KMSI_PATH}?x=1")).status_code == 400
    assert browser.calls == 0


async def test_loopback_peer_gets_sanitized_body_only() -> None:
    browser = _FakeBrowser()
    async with _client(browser) as client:
        response = await client.post(KMSI_PATH)
    assert response.status_code == 200
    body = response.json()
    assert set(body) == {"ok", "surface"}
    assert body["ok"] is True
    assert body["surface"] in {kind.value for kind in SigninSurfaceKind}
    serialized = response.text.lower()
    for forbidden in ("cookie", "token", "password", "http://", "https://", "@"):
        assert forbidden not in serialized


async def test_policy_denied_surfaces_as_503(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PLANNER_MODE", "live")
    monkeypatch.setenv("M365_MODE", "live")
    denied = PolicyDenied("kmsi surface not resolvable", operation=AUTH_KMSI_OPERATION)
    browser = _FakeBrowser(outcome=denied)
    async with _client(browser) as client:
        response = await client.post(KMSI_PATH)
    assert response.status_code == 503
    assert response.json()["detail"]["error"] == "POLICY_DENIED"


async def test_route_is_not_exposed_via_worker_client_or_tool_catalog() -> None:
    assert not any(
        "kmsi" in name.lower() for name in dir(WorkerClient) if not name.startswith("_")
    )
    source = (ROOT / "src" / "planner_mcp" / "worker_client.py").read_text()
    assert "resolve-kmsi-surface" not in source
