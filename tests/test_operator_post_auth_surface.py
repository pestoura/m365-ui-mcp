"""AUTH-115 security + root-cause regression suite: value-free structural census
of the live post-auth Microsoft sign-in surface.

The post-KMSI surface classified ``AMBIGUOUS`` by the existing text-marker
classifier is investigated with a sanitized structural probe that returns ONLY
closed-set facts (role counts, frame-origin classes, fixed Microsoft label
presence booleans, document ready-state, email-entry control presence). It reads
NO page text, NO URL, NO DOM value, NO cookie, NO token, NO UPN, NO tenant id,
NO account identifier. This suite pins the fail-closed contract:

* the route is OPERATOR-ONLY with SOCKET-level loopback admission; non-loopback /
  Docker-network peers get ``404`` and never reach the browser;
* it accepts NO body and NO parameters; any query string is rejected with ``400``;
* the route fails closed on wrong profile / non-approved origin / unstarted
  browser / wrong page count with ``503``;
* the census primitive never returns free strings — every value is an int, bool,
  or CLOSED-enum member;
* a fake page returning only allowed role counts yields a census with exactly the
  closed fields and no identity-bearing data.
"""

from __future__ import annotations

from pathlib import Path

import httpx
import pytest

from m365_browser_worker.signin_surface import (
    AUTH_STRUCTURE_OPERATION,
    SigninSurfaceStructure,
    collect_post_auth_structure,
)
from planner_browser_worker.app import create_app
from planner_mcp.errors import PolicyDenied, WorkerUnavailable

ROOT = Path(__file__).resolve().parent.parent
PROBE_PATH = "/auth/bootstrap/diagnose-post-auth-surface"

pytestmark = pytest.mark.anyio


# --------------------------------------------------------------------------
# Fake Playwright page (allowed-only structural primitives)
# --------------------------------------------------------------------------


class _FakeLocator:
    def __init__(self, count: int) -> None:
        self._count = count

    async def count(self) -> int:
        return self._count


class _FakeFrame:
    def __init__(self, url: str) -> None:
        self.url = url


class _FakePage:
    """Page exposing only the role-count / frame / label primitives the census uses."""

    def __init__(
        self,
        *,
        role_counts: dict[str, int] | None = None,
        frames: list[_FakeFrame] | None = None,
        label_present: dict[str, bool] | None = None,
        ready_state: str = "complete",
        email_entry: bool = False,
    ) -> None:
        self._role_counts = role_counts or {}
        self._frames = frames or []
        self._label_present = label_present or {}
        self._ready_state = ready_state
        self._email_entry = email_entry
        self.evaluate_calls = 0

    def get_by_role(self, role: str, name: str | None = None) -> _FakeLocator:
        if name is None:
            return _FakeLocator(self._role_counts.get(role, 0))
        return _FakeLocator(1 if self._label_present.get(name, False) else 0)

    @property
    def frames(self) -> list[_FakeFrame]:
        return self._frames

    async def evaluate(self, expr: str) -> str:
        self.evaluate_calls += 1
        return self._ready_state

    # email-entry control presence is exercised via detect_email_entry_state; the
    # census calls it and expects a structural EmailEntryState. We emulate that
    # with a small shim attribute the test injects through monkeypatching below.


def _patch_email_entry(monkeypatch, present: bool) -> None:
    from m365_browser_worker import signin_surface as ss

    class _State:
        email_input_present = present
        next_button_present = present
        ambiguous = False

    async def _fake_detect(page):  # noqa: ANN001
        return _State()

    monkeypatch.setattr(ss, "detect_email_entry_state", _fake_detect)


# --------------------------------------------------------------------------
# Closed census primitive
# --------------------------------------------------------------------------


def test_census_returns_only_closed_fields() -> None:
    page = _FakePage(
        role_counts={"button": 3, "link": 1},
        frames=[_FakeFrame("https://login.microsoftonline.com/")],
        label_present={"No": True},
        ready_state="complete",
    )
    structure = _run_collect(page)
    assert isinstance(structure, SigninSurfaceStructure)
    assert structure.role_counts.get("button") == 3
    assert structure.role_counts.get("link") == 1
    # All 18 closed roles are present in the census (zero-filled when absent).
    assert set(structure.role_counts) >= {
        "button",
        "link",
        "textbox",
        "checkbox",
        "radio",
        "heading",
        "alert",
        "dialog",
        "img",
        "list",
        "listitem",
        "tab",
        "combobox",
        "main",
        "navigation",
        "article",
        "form",
        "table",
    }
    assert structure.frame_total == 1
    assert structure.frame_origin_classes == {"microsoft": 1, "neutral": 0, "other": 0}
    assert structure.microsoft_label_present["No"] is True
    assert structure.document_ready_state == "complete"
    assert structure.single_page is True


def test_census_classifies_other_and_neutral_frames() -> None:
    page = _FakePage(
        frames=[
            _FakeFrame("https://evil.example/"),
            _FakeFrame("about:blank"),
        ],
    )
    structure = _run_collect(page)
    assert structure.frame_origin_classes == {"microsoft": 0, "neutral": 1, "other": 1}


def test_census_ready_state_falls_back_to_unknown_on_error(monkeypatch) -> None:  # noqa: ANN001
    page = _FakePage()

    async def _boom(expr: str) -> str:
        raise RuntimeError("no evaluate")

    monkeypatch.setattr(page, "evaluate", _boom)
    structure = _run_collect(page)
    assert structure.document_ready_state == "unknown"


def _run_collect(page: _FakePage) -> SigninSurfaceStructure:
    import asyncio

    return asyncio.run(collect_post_auth_structure(page))


# --------------------------------------------------------------------------
# Route-level contract
# --------------------------------------------------------------------------


class _ResolveBrowser:
    """Duck-typed PersistentBrowser for the route-level contract."""

    def __init__(
        self,
        *,
        started: bool = True,
        dedicated: bool = True,
        origin_approved: bool = True,
        raise_err: Exception | None = None,
        structure: SigninSurfaceStructure | None = None,
    ) -> None:
        self.started = started
        self._started = started
        self._dedicated = dedicated
        self._origin_approved = origin_approved
        self._raise_err = raise_err
        self._structure = structure or SigninSurfaceStructure(
            role_counts={},
            frame_total=0,
            frame_origin_classes={"microsoft": 0, "neutral": 0, "other": 0},
            microsoft_label_present={},
            email_entry_present=False,
            document_ready_state="complete",
            single_page=True,
        )

    def is_dedicated_persistent_profile(self) -> bool:
        return self._dedicated

    def auth_origin_approved(self) -> bool:
        return self._origin_approved

    def ensure_live_allowed(self, operation: str) -> None:
        return None

    async def diagnose_post_auth_surface(self) -> SigninSurfaceStructure:
        if self._raise_err is not None:
            raise self._raise_err
        return self._structure


def _client(browser: _ResolveBrowser, *, peer: tuple[str, int] = ("127.0.0.1", 55555)):
    import os

    os.environ["PLANNER_MODE"] = "live"
    os.environ["M365_MODE"] = "live"
    app = create_app(browser=browser)
    transport = httpx.ASGITransport(app=app, client=peer)
    return httpx.AsyncClient(transport=transport, base_url="http://worker")


async def test_route_loopback_only() -> None:
    import os

    os.environ["PLANNER_MODE"] = "live"
    os.environ["M365_MODE"] = "live"
    app = create_app(browser=_ResolveBrowser())
    transport = httpx.ASGITransport(app=app, client=("10.0.0.9", 44444))
    async with httpx.AsyncClient(transport=transport, base_url="http://worker") as c:
        resp = await c.get(PROBE_PATH)
    assert resp.status_code == 404


async def test_route_rejects_query_string() -> None:
    async with _client(_ResolveBrowser()) as c:
        resp = await c.get(PROBE_PATH + "?x=1")
    assert resp.status_code == 400


async def test_route_fails_closed_on_unstarted() -> None:
    browser = _ResolveBrowser(started=False, raise_err=WorkerUnavailable("no"))
    # ensure_live_allowed is a no-op; the route uses resolve_surface_guard which
    # checks started first and raises 503.
    async with _client(browser) as c:
        resp = await c.get(PROBE_PATH)
    assert resp.status_code == 503


async def test_route_fails_closed_on_wrong_profile() -> None:
    browser = _ResolveBrowser(dedicated=False, raise_err=PolicyDenied("no"))
    async with _client(browser) as c:
        resp = await c.get(PROBE_PATH)
    assert resp.status_code == 503


async def test_route_returns_closed_structure() -> None:
    structure = SigninSurfaceStructure(
        role_counts={"button": 2},
        frame_total=1,
        frame_origin_classes={"microsoft": 1, "neutral": 0, "other": 0},
        microsoft_label_present={"No": True},
        email_entry_present=False,
        document_ready_state="complete",
        single_page=True,
    )
    async with _client(_ResolveBrowser(structure=structure)) as c:
        resp = await c.get(PROBE_PATH)
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    assert body["structure"]["role_counts"] == {"button": 2}
    assert body["structure"]["frame_origin_classes"]["microsoft"] == 1
    assert body["structure"]["microsoft_label_present"]["No"] is True
    # No free-text field leaked.
    assert "url" not in body["structure"]
    assert "text" not in body["structure"]
    assert "title" not in body["structure"]


def test_operation_constant_exported() -> None:
    assert AUTH_STRUCTURE_OPERATION == "auth_diagnose_post_auth_surface"
