"""RED/GREEN/TDD tests for the live-worker UI attestation probe (UI-AUTH-001).

The mechanism reuses the ALREADY-RUNNING Playwright ``browser._context`` (the
dedicated persistent professional profile) to collect sanitized UI-attestation
evidence for the ``planner.plan-surface`` and ``planner.task-surface``
fragments. It is operator-only (socket-loopback GET), read-only, and fail-closed:
it never opens a second persistent context, never returns DOM text / URLs /
cookies / tokens / identity, and never invents selectors (CORE-019).

Pre-implementation this module must FAIL TO IMPORT (RED). After implementation it
turns GREEN.
"""

from __future__ import annotations

import asyncio
import os
from collections.abc import Iterator
from pathlib import Path

import httpx
import pytest

from m365_browser_worker.live_attestation_probe import (
    PLANNER_SURFACE_FRAGMENT_IDS,
    LiveProbeError,
    probe_live_surface_fragment,
)
from m365_mcp.ui_contract_store import UIContractFragment, UIContractSet
from planner_browser_worker.app import create_app

PROBE_PATH = "/auth/bootstrap/probe-planner-surface"

ROOT = Path(__file__).resolve().parent.parent


# --------------------------------------------------------------------------
# Test doubles (mirror tests/test_auth_bootstrap_collect_observation.py)
# --------------------------------------------------------------------------


class _FakeLocator:
    def __init__(self, count: int) -> None:
        self._count = count

    async def count(self) -> int:
        return self._count


class _FakePage:
    def __init__(self, behaviors: dict[tuple[str, str, str | None], int]) -> None:
        self._behaviors = behaviors
        self.url = "https://planner.cloud.microsoft/"

    def _resolve(self, strategy: str, value: str, name: str | None) -> _FakeLocator:
        return _FakeLocator(self._behaviors.get((strategy, value, name), 1))

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


class _FakeContext:
    def __init__(self, pages: list[_FakePage] | None = None) -> None:
        self.pages = pages if pages is not None else []


class _ProbeBrowser:
    """Duck-typed PersistentBrowser exposing the probe-relevant surface."""

    def __init__(
        self,
        *,
        started: bool = True,
        dedicated: bool = True,
        planner_web_surface_present: bool = True,
        common_auth_attested: bool = True,
        pages: int = 1,
        page_behaviors: dict[tuple[str, str, str | None], int] | None = None,
    ) -> None:
        self._started = started
        self._dedicated = dedicated
        self._planner_web_surface_present = planner_web_surface_present
        self._common_auth_attested = common_auth_attested
        self._page_behaviors = page_behaviors or {}
        self._context = _FakeContext(
            [_FakePage(self._page_behaviors) for _ in range(max(pages, 0))]
        )

    @property
    def started(self) -> bool:
        return self._started

    def is_dedicated_persistent_profile(self) -> bool:
        return self._dedicated

    def planner_web_surface_present(self) -> bool:
        return self._planner_web_surface_present

    def auth_origin_approved(self) -> bool:
        return True

    def common_auth_attested(self) -> bool:
        return self._common_auth_attested

    def ensure_live_allowed(self, operation: str) -> None:
        return None


# --------------------------------------------------------------------------
# Fixtures
# --------------------------------------------------------------------------


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
# RED will fail here: the module / symbols above do not exist yet.
# --------------------------------------------------------------------------


def test_fragment_allowlist_is_fixed() -> None:
    assert PLANNER_SURFACE_FRAGMENT_IDS == (
        "planner.plan-surface",
        "planner.task-surface",
    )


def test_probe_rejects_unknown_fragment() -> None:
    browser = _ProbeBrowser()
    with pytest.raises(LiveProbeError):
        # Not in the allowlist: fail closed before any observation.
        asyncio.run(
            probe_live_surface_fragment(browser, fragment_id="common.auth.email")
        )


def test_probe_fails_closed_when_not_on_planner_surface() -> None:
    browser = _ProbeBrowser(planner_web_surface_present=False)
    with pytest.raises(LiveProbeError):
        asyncio.run(
            probe_live_surface_fragment(browser, fragment_id="planner.plan-surface")
        )


def test_probe_fails_closed_on_ambiguous_page_set() -> None:
    browser = _ProbeBrowser(pages=2)
    with pytest.raises(LiveProbeError):
        asyncio.run(
            probe_live_surface_fragment(browser, fragment_id="planner.plan-surface")
        )


def test_probe_reports_no_locator_for_unlocatable_selector(
    live_env,
) -> None:
    # The live fragment JSON ships selectors with NO declared locators plan
    # (value:null, no "locators"). The probe must report NO_LOCATOR honestly;
    # it must NEVER invent a selector. This is the real known blocker.
    browser = _ProbeBrowser()
    result = asyncio.run(
        probe_live_surface_fragment(browser, fragment_id="planner.plan-surface")
    )
    assert result["fragment_id"] == "planner.plan-surface"
    assert result["surface_present"] is True
    assert result["page_count"] == 1
    assert result["selectors"]
    for sel in result["selectors"]:
        assert sel["result"] == "NO_LOCATOR"
        assert "structural_digest" not in sel
    assert result["all_unique_match"] is False


def test_probe_unique_match_with_declared_locator(
    live_env,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Synthetic fragment that DOES declare a locators plan, with an injected
    # live_probe returning exactly one match. Proves the UNIQUE_MATCH + digest
    # path without needing a real Planner DOM render.
    synthetic = UIContractSet(
        set_version="0.1.0",
        legacy_version="0.1.0",
        fragments=(
            UIContractFragment(
                fragment_id="planner.plan-surface",
                fragment_version="0.1.0",
                scope="surface",
                application="planner",
                surface="planner-premium-web",
                capability_keys=("plans.read",),
                attested=False,
                attestation_status="UNVERIFIED_LIVE",
                selectors={
                    "plan.list_container": {
                        "value": None,
                        "status": "UNVERIFIED_LIVE",
                        "locators": [
                            {"strategy": "role", "value": "list", "name": "Plans"}
                        ],
                    }
                },
            ),
        ),
    )
    monkeypatch.setattr(
        "m365_browser_worker.live_attestation_probe.load_ui_contract_set",
        lambda: synthetic,
    )
    browser = _ProbeBrowser()
    result = asyncio.run(
        probe_live_surface_fragment(
            browser,
            fragment_id="planner.plan-surface",
            live_probe=lambda *a, **k: 1,
        )
    )
    assert len(result["selectors"]) == 1
    sel = result["selectors"][0]
    assert sel["selector_key"] == "plan.list_container"
    assert sel["result"] == "UNIQUE_MATCH"
    assert sel["structural_digest"].startswith("sha256:")
    # The digest must be the canonical value-free shape, not a content hash.
    assert len(sel["structural_digest"]) == len("sha256:") + 64
    assert result["all_unique_match"] is True


async def test_route_loopback_peer_accepted(live_env) -> None:
    browser = _ProbeBrowser()
    app = create_app(browser=browser)
    async with _client(app) as client:
        response = await client.get(PROBE_PATH)
    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert len(body["fragments"]) == 2
    assert {f["fragment_id"] for f in body["fragments"]} == set(
        PLANNER_SURFACE_FRAGMENT_IDS
    )
    # No content/identity leakage: only IDs, results, digests.
    for frag in body["fragments"]:
        assert "contract_set_digest" in frag
        for sel in frag["selectors"]:
            assert sel["result"] in ("NO_LOCATOR", "UNIQUE_MATCH", "NO_MATCH", "AMBIGUOUS")


async def test_route_docker_network_peer_denied(live_env) -> None:
    browser = _ProbeBrowser()
    app = create_app(browser=browser)
    async with _client(app, peer=("172.18.0.5", 5555)) as client:
        response = await client.get(PROBE_PATH)
    assert response.status_code == 404


async def test_route_query_string_rejected(live_env) -> None:
    browser = _ProbeBrowser()
    app = create_app(browser=browser)
    async with _client(app) as client:
        response = await client.get(f"{PROBE_PATH}?x=1")
    assert response.status_code == 400
    assert response.json()["detail"]["error"] == "INVALID_REQUEST"


async def test_route_not_on_planner_surface_fails_closed(live_env) -> None:
    # Broker precondition (AUTHENTICATED + VERIFIED surface) fails: 503.
    browser = _ProbeBrowser(
        planner_web_surface_present=False, common_auth_attested=False
    )
    app = create_app(browser=browser)
    async with _client(app) as client:
        response = await client.get(PROBE_PATH)
    assert response.status_code == 503


def test_route_is_get_only() -> None:
    app = create_app()
    route_methods = [
        getattr(r, "methods", set()) or set()
        for r in app.routes
        if getattr(r, "path", "") == PROBE_PATH
    ]
    flat = {m for group in route_methods for m in group}
    assert "GET" in flat
    assert "POST" not in flat
