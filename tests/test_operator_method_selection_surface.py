"""AUTH-115 security regression suite: deterministic fail-closed resolution of
the Microsoft Entra ID ``METHOD_SELECTION`` -> ``Microsoft Authenticator``
approval surface.

The live headless operator run reaches this surface when Microsoft presents a
verification-method chooser that uniquely resolves to the ``Approve a request on
my Authenticator app`` control (no number/code entry, no cached identity
selection). The only action permitted is a single click on ONE fixed Microsoft
Authenticator control.

This suite pins the fail-closed contract with a STRICTER global uniqueness
guarantee than AUTH-114 (KMSI):

* the Authenticator action is matched ONLY from a CLOSED set of exact Microsoft
  labels and ONLY when the TOTAL matching candidate count across the entire
  closed set of labels equals EXACTLY one. The deployed contract requires the
  resolver to surface-match via ``page.get_by_text(label, exact=True)`` — not by
  ARIA role (button/link). A single label that itself counts to exactly one is
  NOT sufficient if any other closed label also matches — the global candidate
  count must be exactly 1, so a split of ``1 + 1`` across two labels (global 2)
  is rejected, as is any per-pair count of 2 or more (global >= 2). No regex,
  no wildcard, no ``first`` of many, no caller-supplied selector;
* the resolver acts ONLY when the surface classifies as ``METHOD_SELECTION``;
  every other surface (email entry, chooser, KMSI, consent, error, ambiguous,
  unknown) is left untouched and reported fail-closed;
* the resolver NEVER types a credential (no fill/type), never selects a cached
  identity, never clicks Sign in, never navigates by URL/selector (no
  goto/press), and never returns URL/DOM/page text/cookie/token/UPN/tenant/
  account identifier;
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
    AUTH_METHOD_SELECTION_OPERATION,
    AUTHENTICATOR_METHOD_LABELS,
    SIGNIN_OPTIONS_LABELS,
    SigninSurfaceKind,
    click_authenticator_method,
    click_signin_options,
    resolve_method_selection_surface,
)
from planner_browser_worker.app import create_app
from planner_mcp.errors import PolicyDenied
from planner_mcp.worker_client import WorkerClient

ROOT = Path(__file__).resolve().parent.parent
METHOD_SELECTION_PATH = "/auth/bootstrap/resolve-method-selection-surface"

pytestmark = pytest.mark.anyio


# --------------------------------------------------------------------------
# Test doubles
# --------------------------------------------------------------------------


class _FakeLocator:
    def __init__(
        self,
        count: int,
        *,
        label: str | None = None,
        exact: bool | None = None,
    ) -> None:
        self._count = count
        self.label = label
        self.exact = exact
        self.clicks = 0

    async def count(self) -> int:
        return self._count

    @property
    def first(self) -> _FakeLocator:
        return self

    async def click(self, timeout: int | None = None) -> None:
        self.clicks += 1


class _FakeMethodSelectionPage:
    """Page exposing Authenticator controls for fixed EXACT-TEXT labels only.

    Mirrors the deployed contract: the resolver must match the Microsoft
    Authenticator approval control via ``page.get_by_text(label, exact=True)``,
    NOT via ARIA role (button/link). The fake records every ``get_by_text`` call
    so assertions can prove the resolver used exact-text matching.
    """

    def __init__(self, matches: dict[str, int] | None = None) -> None:
        self._matches = matches or {}
        self.locators: list[_FakeLocator] = []
        self.text_calls: list[tuple[str, bool]] = []
        self.fill_calls: list[tuple[str, str]] = []
        self.goto_calls: list[str] = []
        self.type_calls: list[tuple[str, str]] = []
        self.press_calls: list[str] = []
        self.timeout_calls: list[int] = []

    async def wait_for_timeout(self, timeout: int) -> None:
        self.timeout_calls.append(timeout)

    def get_by_text(self, text: str, *, exact: bool = False) -> _FakeLocator:
        self.text_calls.append((text, exact))
        locator = _FakeLocator(self._matches.get(text, 0), label=text, exact=exact)
        self.locators.append(locator)
        return locator

    async def fill(self, selector: str, value: str) -> None:  # pragma: no cover
        self.fill_calls.append((selector, value))

    async def goto(self, url: str) -> None:  # pragma: no cover
        self.goto_calls.append(url)

    async def type(self, selector: str, value: str) -> None:  # pragma: no cover
        self.type_calls.append((selector, value))

    async def press(self, selector: str, key: str) -> None:  # pragma: no cover
        self.press_calls.append(f"{selector}:{key}")


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

    async def resolve_method_selection_surface(self) -> SigninSurfaceKind:
        self.calls += 1
        if isinstance(self._outcome, Exception):
            raise self._outcome
        return self._outcome or SigninSurfaceKind.METHOD_SELECTION


def _client(browser: _FakeBrowser, *, peer: tuple[str, int] = ("127.0.0.1", 55555)):
    app = create_app(browser=browser)
    transport = httpx.ASGITransport(app=app, client=peer)
    return httpx.AsyncClient(transport=transport, base_url="http://worker")


# --------------------------------------------------------------------------
# Closed label set / strict GLOBAL uniqueness
# --------------------------------------------------------------------------


def test_authenticator_labels_are_the_exact_closed_six_element_set() -> None:
    assert isinstance(AUTHENTICATOR_METHOD_LABELS, tuple)
    # Closed, exact, nothing more and nothing less: the six official Microsoft
    # Authenticator approval labels across en-US (two variants) / pt-BR /
    # pt-PT, plus the two official "Send notification" / "Enviar notificação"
    # labels the live method-selection surface can render.
    assert AUTHENTICATOR_METHOD_LABELS == (
        "Approve a request on my Authenticator app",
        "Aprovar uma solicitação no meu aplicativo Authenticator",
        "Aprovar um pedido na minha aplicação de Microsoft Authenticator",
        "Approve a request on my Microsoft Authenticator app",
        "Send notification",
        "Enviar notificação",
    )
    assert len(AUTHENTICATOR_METHOD_LABELS) == 6
    for label in AUTHENTICATOR_METHOD_LABELS:
        assert isinstance(label, str)
        assert label.strip() == label
        assert "*" not in label
        assert ".*" not in label
    # The fourth English variant is a DISTINCT closed member, not a duplicate
    # of the shorter en-US label.
    assert len(AUTHENTICATOR_METHOD_LABELS) == len(set(AUTHENTICATOR_METHOD_LABELS))


async def test_click_requires_exactly_one_global_candidate() -> None:
    label = AUTHENTICATOR_METHOD_LABELS[0]
    # A single label counting to exactly 1 -> click once, using exact text.
    unique = _FakeMethodSelectionPage({label: 1})
    assert await click_authenticator_method(unique) is True
    assert sum(locator.clicks for locator in unique.locators) == 1
    # The resolver must match via exact text, never by role button/link.
    assert any(
        t == label and exact is True for (t, exact) in unique.text_calls
    )

    # A single label counting to 2 -> global total >= 2 -> never click.
    duplicate = _FakeMethodSelectionPage({label: 2})
    assert await click_authenticator_method(duplicate) is False
    assert all(locator.clicks == 0 for locator in duplicate.locators)

    # Zero candidates anywhere -> False, click nothing.
    empty = _FakeMethodSelectionPage({})
    assert await click_authenticator_method(empty) is False
    assert all(locator.clicks == 0 for locator in empty.locators)


async def test_click_rejects_split_uniqueness_across_closed_set() -> None:
    # The STRICTER contract: two distinct labels each counting to exactly 1
    # yields a GLOBAL total of 2, which is NOT strictly unique -> click nothing.
    split = _FakeMethodSelectionPage(
        {
            AUTHENTICATOR_METHOD_LABELS[0]: 1,
            AUTHENTICATOR_METHOD_LABELS[1]: 1,
        }
    )
    assert await click_authenticator_method(split) is False
    assert all(locator.clicks == 0 for locator in split.locators)


async def test_click_uses_get_by_text_with_exact_true() -> None:
    # The deployed contract MUST resolve the Authenticator control via exact
    # text, NOT via ARIA role (button/link). This fails while production still
    # uses page.get_by_role(role, name=label) instead of get_by_text.
    page = _FakeMethodSelectionPage({AUTHENTICATOR_METHOD_LABELS[0]: 1})
    await click_authenticator_method(page)
    assert any(
        t == AUTHENTICATOR_METHOD_LABELS[0] and exact is True
        for (t, exact) in page.text_calls
    )


async def test_click_never_fills_types_navigates_or_presses() -> None:
    page = _FakeMethodSelectionPage({AUTHENTICATOR_METHOD_LABELS[0]: 1})
    await click_authenticator_method(page)
    assert page.fill_calls == []
    assert page.type_calls == []
    assert page.goto_calls == []
    assert page.press_calls == []


async def test_click_absent_control_is_false_not_a_guess() -> None:
    page = _FakeMethodSelectionPage({})
    assert await click_authenticator_method(page) is False
    assert all(locator.clicks == 0 for locator in page.locators)


# --------------------------------------------------------------------------
# Surface-scoped resolution
# --------------------------------------------------------------------------


async def test_resolver_acts_only_on_method_selection() -> None:
    # The live METHOD_SELECTION surface renders ONLY "Sign in" + "Sign-in
    # options" (no directly visible Authenticator control). The resolver must
    # reveal the method list (stage 1) and then approve via Authenticator
    # (stage 2), advancing through both stages.
    page = _FakeMethodSelectionPage(
        {
            SIGNIN_OPTIONS_LABELS[0]: 1,
            AUTHENTICATOR_METHOD_LABELS[0]: 1,
        }
    )
    readings = [
        "Sign in\nSign-in options",  # initial METHOD_SELECTION, only reveal control
        "Choose how you want to sign in\nApprove a request on my Authenticator app",
        "Approving your sign-in",  # post-authenticator terminal read
    ]

    class _StepReader:
        def __init__(self, seq: list[str]) -> None:
            self._seq = seq
            self._idx = 0

        async def read(self) -> str:
            text = self._seq[min(self._idx, len(self._seq) - 1)]
            self._idx += 1
            return text

    reader = _StepReader(readings)
    resolution = await resolve_method_selection_surface(page, reader.read)
    assert resolution.advanced is True
    assert sum(locator.clicks for locator in page.locators) == 2


@pytest.mark.parametrize(
    "text",
    [
        "Enter your email, phone, or Skype",
        "Pick an account",
        "Stay signed in?",
        "Something went wrong",
        "",
    ],
)
async def test_resolver_never_acts_on_other_surfaces(text: str) -> None:
    page = _FakeMethodSelectionPage(
        {AUTHENTICATOR_METHOD_LABELS[0]: 1}
    )
    resolution = await resolve_method_selection_surface(page, _reader(text))
    assert resolution.advanced is False
    assert sum(locator.clicks for locator in page.locators) == 0


async def test_resolver_fails_closed_when_control_absent() -> None:
    page = _FakeMethodSelectionPage({})
    resolution = await resolve_method_selection_surface(
        page, _reader("Choose how you want to sign in")
    )
    assert resolution.advanced is False
    assert resolution.terminal_surface is SigninSurfaceKind.METHOD_SELECTION


# -------------------------------------------------------------------------
# AUTH-115 two-stage flow: METHOD_SELECTION with only "Sign in" +
# "Sign-in options" must reveal the method list before the Authenticator
# control becomes clickable.
# -------------------------------------------------------------------------


async def test_click_signin_options_requires_exactly_one_global_candidate() -> None:
    label = SIGNIN_OPTIONS_LABELS[0]
    # A single label counting to exactly 1 -> click once, using exact text.
    unique = _FakeMethodSelectionPage({label: 1})
    assert await click_signin_options(unique) is True
    assert sum(locator.clicks for locator in unique.locators) == 1
    assert any(
        t == label and exact is True for (t, exact) in unique.text_calls
    )

    # A single label counting to 2 -> global total >= 2 -> never click.
    duplicate = _FakeMethodSelectionPage({label: 2})
    assert await click_signin_options(duplicate) is False
    assert all(locator.clicks == 0 for locator in duplicate.locators)

    # Zero candidates anywhere -> False, click nothing.
    empty = _FakeMethodSelectionPage({})
    assert await click_signin_options(empty) is False
    assert all(locator.clicks == 0 for locator in empty.locators)


async def test_click_signin_options_rejects_split_uniqueness() -> None:
    # Two distinct labels each counting to exactly 1 yields a GLOBAL total of 2,
    # which is NOT strictly unique -> click nothing.
    split = _FakeMethodSelectionPage(
        {
            SIGNIN_OPTIONS_LABELS[0]: 1,
            SIGNIN_OPTIONS_LABELS[1]: 1,
        }
    )
    assert await click_signin_options(split) is False
    assert all(locator.clicks == 0 for locator in split.locators)


async def test_click_signin_options_uses_get_by_text_with_exact_true() -> None:
    page = _FakeMethodSelectionPage({SIGNIN_OPTIONS_LABELS[0]: 1})
    await click_signin_options(page)
    assert any(
        t == SIGNIN_OPTIONS_LABELS[0] and exact is True
        for (t, exact) in page.text_calls
    )


async def test_click_signin_options_never_fills_types_navigates_or_presses() -> None:
    page = _FakeMethodSelectionPage({SIGNIN_OPTIONS_LABELS[0]: 1})
    await click_signin_options(page)
    assert page.fill_calls == []
    assert page.type_calls == []
    assert page.goto_calls == []
    assert page.press_calls == []


async def test_resolver_two_stage_signin_options_then_authenticator() -> None:
    # Initial surface renders ONLY "Sign in" + "Sign-in options" (no directly
    # visible Authenticator control). Stage 1 reveals the method list; stage 2
    # reuses click_authenticator_method on the now-expanded surface.
    page = _FakeMethodSelectionPage(
        {
            SIGNIN_OPTIONS_LABELS[0]: 1,
            AUTHENTICATOR_METHOD_LABELS[0]: 1,
        }
    )

    readings = [
        "Sign in\nSign-in options",  # initial METHOD_SELECTION, only reveal control
        "Choose how you want to sign in\nApprove a request on my Authenticator app",
        "Approving your sign-in",  # post-authenticator terminal read
    ]

    class _MultiReader:
        def __init__(self, seq: list[str]) -> None:
            self._seq = seq
            self._idx = 0

        async def read(self) -> str:
            text = self._seq[min(self._idx, len(self._seq) - 1)]
            self._idx += 1
            return text

    reader = _MultiReader(readings)
    resolution = await resolve_method_selection_surface(page, reader.read)
    # Both stages clicked exactly once; resolution advanced.
    assert resolution.advanced is True
    assert sum(locator.clicks for locator in page.locators) == 2
    # The reveal click must be followed by an explicit render wait before the
    # re-read that drives stage 2.
    assert page.timeout_calls == [1000]
    # Stage 1 matched via exact text "Sign-in options".
    assert any(
        t == SIGNIN_OPTIONS_LABELS[0] and exact is True
        for (t, exact) in page.text_calls
    )
    # Stage 2 reused the Authenticator exact-text matcher.
    assert any(
        t == AUTHENTICATOR_METHOD_LABELS[0] and exact is True
        for (t, exact) in page.text_calls
    )


async def test_resolver_direct_method_selection_clicks_authenticator_without_reveal() -> None:
    page = _FakeMethodSelectionPage({AUTHENTICATOR_METHOD_LABELS[0]: 1})
    readings = [
        "Choose how you want to sign in\nApprove a request on my Authenticator app",
        "Approving your sign-in",
    ]

    class _DirectReader:
        def __init__(self, seq: list[str]) -> None:
            self._seq = seq
            self._idx = 0

        async def read(self) -> str:
            text = self._seq[min(self._idx, len(self._seq) - 1)]
            self._idx += 1
            return text

    resolution = await resolve_method_selection_surface(page, _DirectReader(readings).read)
    assert resolution.advanced is True
    assert sum(locator.clicks for locator in page.locators) == 1
    assert page.timeout_calls == []
    assert not any(text == SIGNIN_OPTIONS_LABELS[0] for text, _exact in page.text_calls)



async def test_resolver_fails_closed_when_multiple_signin_options_controls() -> None:
    # More than one "Sign-in options" candidate is ambiguous -> fail closed
    # without clicking anything.
    page = _FakeMethodSelectionPage(
        {
            SIGNIN_OPTIONS_LABELS[0]: 2,
            AUTHENTICATOR_METHOD_LABELS[0]: 1,
        }
    )
    resolution = await resolve_method_selection_surface(
        page, _reader("Sign in\nSign-in options")
    )
    assert resolution.advanced is False
    assert resolution.terminal_surface is SigninSurfaceKind.AMBIGUOUS
    assert sum(locator.clicks for locator in page.locators) == 0


# -------------------------------------------------------------------------
# Route contract
# -------------------------------------------------------------------------


async def test_non_loopback_peer_gets_404_and_never_touches_browser() -> None:
    browser = _FakeBrowser()
    async with _client(browser, peer=("172.18.0.4", 4444)) as client:
        response = await client.post(METHOD_SELECTION_PATH)
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
        response = await client.post(METHOD_SELECTION_PATH, headers=headers)
    assert response.status_code == 404
    assert browser.calls == 0


async def test_route_rejects_body_and_query() -> None:
    browser = _FakeBrowser()
    async with _client(browser) as client:
        assert (await client.post(METHOD_SELECTION_PATH, json={"x": 1})).status_code == 400
        assert (await client.post(f"{METHOD_SELECTION_PATH}?x=1")).status_code == 400
    assert browser.calls == 0


async def test_loopback_peer_gets_sanitized_body_only() -> None:
    browser = _FakeBrowser()
    async with _client(browser) as client:
        response = await client.post(METHOD_SELECTION_PATH)
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
    denied = PolicyDenied(
        "method selection surface not resolvable",
        operation=AUTH_METHOD_SELECTION_OPERATION,
    )
    browser = _FakeBrowser(outcome=denied)
    async with _client(browser) as client:
        response = await client.post(METHOD_SELECTION_PATH)
    assert response.status_code == 503
    assert response.json()["detail"]["error"] == "POLICY_DENIED"


async def test_route_is_not_exposed_via_worker_client_or_tool_catalog() -> None:
    assert not any(
        "resolve_method_selection_surface" in name
        for name in dir(WorkerClient)
        if not name.startswith("_")
    )
    source = (ROOT / "src" / "planner_mcp" / "worker_client.py").read_text()
    assert "resolve-method-selection-surface" not in source




async def test_click_signin_options_supports_official_other_ways_to_sign_in_label() -> None:
    # RED pin: production SIGNIN_OPTIONS_LABELS must eventually include the
    # official "Other ways to sign in" reveal control rendered on some live
    # METHOD_SELECTION surfaces, and click_signin_options must resolve it via
    # exact-text matching using get_by_text(label, exact=True).
    label = "Other ways to sign in"
    assert label in SIGNIN_OPTIONS_LABELS
    page = _FakeMethodSelectionPage({label: 1})
    assert await click_signin_options(page) is True
    assert sum(locator.clicks for locator in page.locators) == 1
    assert any(
        t == label and exact is True for (t, exact) in page.text_calls
    )


@pytest.mark.parametrize(
    "label",
    [
        "Other ways to sign in",
        "Sign in another way",
        "Use a different verification option",
    ],
)
async def test_click_signin_options_supports_official_microsoft_variants(label: str) -> None:
    # RED pin: production SIGNIN_OPTIONS_LABELS must include all three official
    # Microsoft METHOD_SELECTION reveal-control variants, and click_signin_options
    # must resolve each via exact-text matching using get_by_text(label,
    # exact=True) with exactly one click.
    assert label in SIGNIN_OPTIONS_LABELS
    page = _FakeMethodSelectionPage({label: 1})
    assert await click_signin_options(page) is True
    assert sum(locator.clicks for locator in page.locators) == 1
    assert any(
        t == label and exact is True for (t, exact) in page.text_calls
    )
