"""Focused tests for fragment-scoped ``common.auth`` attestation.

Regression for the semantic bug found in review: ``common_auth_attested()``
previously returned the AGGREGATED common+Planner ``load_status().attested``
signal, so ``common.auth`` attested + Planner fragments UNVERIFIED wrongly
reported LIVE auth UNKNOWN. The fix scopes the auth-state signal to the
``common.auth`` fragment alone, while the strict full-contract ``live_guard`` /
bootstrap-guard deferral stays on the aggregated signal.

State matrix proven:
(1) common.auth UNVERIFIED + planner UNVERIFIED => auth_status UNKNOWN, planner 503.
(2) common.auth ATTESTED + planner UNVERIFIED   => auth_status AUTHENTICATED, planner 503.
(3) common.auth ATTESTED + planner ATTESTED      => auth_status AUTHENTICATED, planner
    capability gate may pass subject to other account/capability gates.
(4) missing common.auth fragment                 => UNKNOWN / fail closed.

Wrong profile / wrong origin denials are preserved.
"""

from __future__ import annotations

import os

import httpx
import pytest

from m365_browser_worker.account_context import AccountContext, AccountContextState
from m365_mcp.ui_contract_store import UIContractFragment, UIContractSet, load_ui_contract_set
from planner_browser_worker.app import create_app
from planner_mcp.auth import AuthState
from planner_mcp.errors import UiContractUnattested
from planner_mcp.ui_contract import common_auth_attested


class _FakeBrowser:
    """Minimal test double of PersistentBrowser's guard-relevant surface."""

    def __init__(
        self,
        *,
        started: bool = False,
        dedicated: bool = False,
        approved_origin: bool = False,
        auth_attested: bool = False,
        full_attested: bool = False,
    ) -> None:
        self._started = started
        self._dedicated = dedicated
        self._approved_origin = approved_origin
        self._auth_attested = auth_attested
        self._full_attested = full_attested

    @property
    def started(self) -> bool:
        return self._started

    def is_dedicated_persistent_profile(self) -> bool:
        return self._dedicated

    def auth_origin_approved(self) -> bool:
        return self._approved_origin

    def common_auth_attested(self) -> bool:
        return self._auth_attested

    def planner_web_surface_present(self) -> bool:
        # The matrix tests exercise the auth-state/UIContract gates, not the
        # post-MFA surface promotion; the positive Planner Web surface signal
        # is intentionally not modeled here (the account context is injected
        # explicitly via account_context_provider in _make_live_app). Returning
        # False keeps live_account_context fail-closed to UNVERIFIED unless a
        # test injects its own provider.
        return False

    def ensure_live_allowed(self, operation: str) -> None:
        if not self._full_attested:
            raise UiContractUnattested(f"blocked {operation}")


def _verified_account_context() -> AccountContext:
    return AccountContext(
        state=AccountContextState.VERIFIED,
        professional=True,
        expected_profile=True,
    )


@pytest.fixture(autouse=True)
def _live_mode_env():
    # Keep PLANNER_MODE/M365_MODE = live for the whole test so endpoint handlers
    # take the LIVE path (create_app reads the mode at request time, not at
    # build time). Restored afterwards to avoid leaking into other tests.
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


def _make_live_app(
    *,
    auth_attested: bool,
    full_attested: bool,
    account_context_provider=None,
    broker_viable: bool = True,
) -> object:
    # Env is held live by the ``_live_mode_env`` fixture for the request path.
    browser = _FakeBrowser(
        started=True,
        dedicated=True,
        approved_origin=True,
        auth_attested=auth_attested,
        full_attested=full_attested,
    )
    # The LIVE auth state (and thus the broker's auth-state gate) is derived from
    # the fragment-scoped common.auth attestation, mirroring live_auth_state().
    def derived_auth_state():
        from planner_mcp.auth import AuthState

        return AuthState.AUTHENTICATED if browser.common_auth_attested() else AuthState.UNKNOWN

    app = create_app(
        browser=browser,
        auth_state_provider=derived_auth_state,
        account_context_provider=account_context_provider or _verified_account_context,
        broker_viability_provider=lambda: broker_viable,
    )
    return app


async def _auth_status_state(app) -> str:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://worker") as client:
        response = await client.get("/auth/status")
        assert response.status_code == 200
        return response.json()["state"]


async def _planner_plans_status(app) -> int:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://worker") as client:
        return (await client.get("/planner/plans")).status_code


async def test_matrix_1_common_and_planner_unverified_unknown_blocked() -> None:
    # (1) common.auth UNVERIFIED + planner UNVERIFIED => UNKNOWN, planner 503.
    app = _make_live_app(auth_attested=False, full_attested=False)
    assert await _auth_status_state(app) == AuthState.UNKNOWN.value
    assert await _planner_plans_status(app) == 503


async def test_matrix_2_common_attested_planner_unverified_auth_but_blocked() -> None:
    # (2) common.auth ATTESTED + planner UNVERIFIED => AUTHENTICATED, planner 503.
    # The fragment-scoped auth signal reports AUTHENTICATED while the strict
    # full-contract read gate still blocks Planner reads (missing planner
    # attestation is NOT masked by common.auth).
    app = _make_live_app(auth_attested=True, full_attested=False)
    assert await _auth_status_state(app) == AuthState.AUTHENTICATED.value
    assert await _planner_plans_status(app) == 503


async def test_matrix_3_common_and_planner_attested_gate_may_pass() -> None:
    # (3) common.auth ATTESTED + planner ATTESTED => AUTHENTICATED and the
    # Planner capability gate is reached (not blocked by UIContract). With a
    # verified professional account context and a viable broker the read
    # returns 200; the UIContract gate itself is open.
    app = _make_live_app(auth_attested=True, full_attested=True)
    assert await _auth_status_state(app) == AuthState.AUTHENTICATED.value
    assert await _planner_plans_status(app) == 200


def test_common_auth_attested_unit_unverified_fragment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Unit level: when BOTH common.auth fragments are present but UNVERIFIED =>
    # False. This proves the function inspects attestation state, not mere
    # fragment presence. (The shipped source contract promotes both fragments to
    # ATTESTED, so the default path returns True; here we force the unverified
    # state to exercise the fail-closed branch.)
    source = load_ui_contract_set()
    unverified = tuple(
        UIContractFragment(
            fragment_id=f.fragment_id,
            fragment_version=f.fragment_version,
            scope=f.scope,
            application=f.application,
            surface=f.surface,
            capability_keys=f.capability_keys,
            attested=False,
            attestation_status="UNVERIFIED_LIVE",
            selectors={
                name: {**meta, "status": "UNVERIFIED_LIVE"}
                for name, meta in f.selectors.items()
            },
        )
        if f.fragment_id in ("common.auth.email", "common.auth.password")
        else f
        for f in source.fragments
    )
    patched = UIContractSet(
        set_version=source.set_version,
        legacy_version=source.legacy_version,
        fragments=unverified,
    )
    monkeypatch.setattr(
        "planner_mcp.ui_contract.load_ui_contract_set", lambda *a, **k: patched
    )
    assert common_auth_attested() is False


def test_common_auth_attested_unit_source_contract_is_promoted() -> None:
    # The shipped source contract promotes both atomic common.auth fragments to
    # ATTESTED by explicit evidence-backed PR promotion, so the default path
    # returns True. Keeps the inverse of the unverified test green.
    assert common_auth_attested() is True


def test_common_auth_attested_unit_missing_fragment_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # (4) Missing a common.auth fragment => fail closed (False). No other
    # fragment's attestation state leaks into the auth signal.
    no_common = UIContractSet(
        set_version="0.2.0",
        legacy_version="0.1.0",
        fragments=tuple(
            f
            for f in load_ui_contract_set().fragments
            if f.fragment_id not in ("common.auth.email", "common.auth.password")
        ),
    )
    monkeypatch.setattr(
        "planner_mcp.ui_contract.load_ui_contract_set", lambda *a, **k: no_common
    )
    assert common_auth_attested() is False


def test_common_auth_attested_unit_attested_fragment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # BOTH common.auth fragments explicitly ATTESTED (fragment + selectors) =>
    # True even when every other fragment stays UNVERIFIED (proves fragment
    # scoping and the both-fragments requirement).
    source = load_ui_contract_set()

    def _attest(fragment: UIContractFragment) -> UIContractFragment:
        attested_selectors = {
            name: {**meta, "status": "ATTESTED"}
            for name, meta in fragment.selectors.items()
        }
        return UIContractFragment(
            fragment_id=fragment.fragment_id,
            fragment_version=fragment.fragment_version,
            scope=fragment.scope,
            application=fragment.application,
            surface=fragment.surface,
            capability_keys=fragment.capability_keys,
            attested=True,
            attestation_status="ATTESTED",
            selectors=attested_selectors,
        )

    common = tuple(
        _attest(f)
        for f in source.fragments
        if f.fragment_id in ("common.auth.email", "common.auth.password")
    )
    # Keep planner fragments UNVERIFIED; only common.auth.* is promoted.
    others = tuple(
        f
        for f in source.fragments
        if f.fragment_id not in ("common.auth.email", "common.auth.password")
    )
    patched = UIContractSet(
        set_version=source.set_version,
        legacy_version=source.legacy_version,
        fragments=(*common, *others),
    )
    monkeypatch.setattr(
        "planner_mcp.ui_contract.load_ui_contract_set", lambda *a, **k: patched
    )
    assert common_auth_attested() is True


def test_common_auth_attested_unit_only_email_attested_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Only one of the two atomic auth fragments attested (email) while password
    # stays UNVERIFIED => False. Both must be effectively attested before AUTH-101
    # may apply credentials. The shipped source promotes BOTH, so we must force
    # the password fragment back to UNVERIFIED to model the single-fragment case.
    source = load_ui_contract_set()

    def _attest(fragment: UIContractFragment) -> UIContractFragment:
        attested_selectors = {
            name: {**meta, "status": "ATTESTED"}
            for name, meta in fragment.selectors.items()
        }
        return UIContractFragment(
            fragment_id=fragment.fragment_id,
            fragment_version=fragment.fragment_version,
            scope=fragment.scope,
            application=fragment.application,
            surface=fragment.surface,
            capability_keys=fragment.capability_keys,
            attested=True,
            attestation_status="ATTESTED",
            selectors=attested_selectors,
        )

    def _unverify(fragment: UIContractFragment) -> UIContractFragment:
        unverified_selectors = {
            name: {**meta, "status": "UNVERIFIED_LIVE"}
            for name, meta in fragment.selectors.items()
        }
        return UIContractFragment(
            fragment_id=fragment.fragment_id,
            fragment_version=fragment.fragment_version,
            scope=fragment.scope,
            application=fragment.application,
            surface=fragment.surface,
            capability_keys=fragment.capability_keys,
            attested=False,
            attestation_status="UNVERIFIED_LIVE",
            selectors=unverified_selectors,
        )

    common = tuple(
        _attest(f) if f.fragment_id == "common.auth.email" else _unverify(f)
        for f in source.fragments
        if f.fragment_id in ("common.auth.email", "common.auth.password")
    )
    others = tuple(
        f
        for f in source.fragments
        if f.fragment_id not in ("common.auth.email", "common.auth.password")
    )
    patched = UIContractSet(
        set_version=source.set_version,
        legacy_version=source.legacy_version,
        fragments=(*common, *others),
    )
    monkeypatch.setattr(
        "planner_mcp.ui_contract.load_ui_contract_set", lambda *a, **k: patched
    )
    assert common_auth_attested() is False


async def test_wrong_profile_denied_pre_attestation() -> None:
    # Wrong/dedicated profile denial is preserved by the bootstrap guard.
    # Env is held live by the ``_live_mode_env`` fixture.
    browser = _FakeBrowser(
        started=True, dedicated=False, approved_origin=True, auth_attested=False
    )
    app = create_app(browser=browser)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport, base_url="http://worker"
    ) as client:
        response = await client.get("/auth/status")
        assert response.status_code == 503
        assert response.json()["detail"]["error"] == "POLICY_DENIED"


async def test_wrong_origin_denied_pre_attestation() -> None:
    # Wrong origin denial is preserved by the bootstrap guard.
    # Env is held live by the ``_live_mode_env`` fixture.
    browser = _FakeBrowser(
        started=True, dedicated=True, approved_origin=False, auth_attested=False
    )
    app = create_app(browser=browser)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport, base_url="http://worker"
    ) as client:
        response = await client.get("/auth/status")
        assert response.status_code == 503
        assert response.json()["detail"]["error"] == "POLICY_DENIED"
