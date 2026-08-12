"""Focused tests for the LIVE UIContract authentication bootstrap deadlock fix.

Covers:
* bootstrap auth allowed only under constrained live conditions;
* mock / non-professional / wrong-origin failures fail closed;
* Planner reads and account reads remain blocked (full-contract guard intact);
* auth bootstrap endpoints emit no secrets / raw content;
* operator observation schema + contract-set digest binding;
* MOCK cannot produce promotion-grade evidence;
* no runtime endpoint mutates source contract JSON / self-promotes ATTESTED.
"""

from __future__ import annotations

import datetime
import hashlib
import importlib.util
import json
import os
from pathlib import Path

import httpx
import pytest

from m365_browser_worker.auth_bootstrap import (
    AuthBootstrapGuard,
    AuthOriginStatus,
    auth_origin_status,
)
from m365_mcp.attestation import (
    AttestationLevel,
    AttestationObservation,
    ObservationSource,
    SelectorObservation,
    SelectorObservationResult,
    build_attestation_campaign,
    evaluate_attestation_observation,
)
from m365_mcp.ui_contract_store import load_ui_contract_set
from planner_browser_worker.app import create_app
from planner_mcp.errors import PolicyDenied, UiContractUnattested, WorkerUnavailable


def _load_collect_live_attestation_observation():
    """Robustly load the operator script by absolute path (CI-proof).

    The repository-root ``scripts`` namespace is not importable in every
    pytest environment (e.g. installed-package CI runs), so we load the module
    file directly via importlib instead of ``import scripts...``. This keeps
    production code, packaging semantics and runtime behavior unchanged.
    """
    script_path = (
        Path(__file__).resolve().parent.parent
        / "scripts"
        / "collect_live_attestation_observation.py"
    )
    spec = importlib.util.spec_from_file_location(
        "collect_live_attestation_observation", str(script_path)
    )
    if spec is None or spec.loader is None:
        raise ImportError(
            f"could not load collect_live_attestation_observation from {script_path}"
        )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_collect_module = _load_collect_live_attestation_observation()
collect_structural_observation = _collect_module.collect_structural_observation


class _FakeBrowser:
    """Test double exposing only the guard-relevant surface of PersistentBrowser."""

    def __init__(
        self,
        *,
        started: bool = False,
        dedicated: bool = False,
        approved_origin: bool = False,
        auth_attested: bool = False,
    ) -> None:
        self._started = started
        self._dedicated = dedicated
        self._approved_origin = approved_origin
        self._auth_attested = auth_attested
        self.strict_raised = False

    @property
    def started(self) -> bool:
        return self._started

    def is_dedicated_persistent_profile(self) -> bool:
        return self._dedicated

    def auth_origin_approved(self) -> bool:
        return self._approved_origin

    def common_auth_attested(self) -> bool:
        return self._auth_attested

    def ensure_live_allowed(self, operation: str) -> None:
        self.strict_raised = True
        raise UiContractUnattested(f"blocked {operation}")


def _guard(
    *,
    started: bool = False,
    dedicated: bool = False,
    approved_origin: bool = False,
    auth_attested: bool = False,
) -> AuthBootstrapGuard:
    browser = _FakeBrowser(
        started=started,
        dedicated=dedicated,
        approved_origin=approved_origin,
        auth_attested=auth_attested,
    )
    return AuthBootstrapGuard(
        browser_started_provider=lambda: browser.started,
        dedicated_profile_provider=browser.is_dedicated_persistent_profile,
        approved_auth_origin_provider=browser.auth_origin_approved,
        auth_attested_provider=browser.common_auth_attested,
        strict_live_guard=browser.ensure_live_allowed,
    )


def test_auth_origin_status_never_exposes_url() -> None:
    # URLs are reduced to a closed status; the value is not returned anywhere.
    assert auth_origin_status(()) is AuthOriginStatus.NO_ACTIVE_PAGE


# --- Neutral bootstrap origin regression suite (PR #596 follow-up) ---
# about:blank and chrome://newtab are harmless placeholders that carry no
# identity, tenant or web origin. They must NOT be treated as
# NON_APPROVED_ORIGIN (the false-positive that blocked bootstrap). No http/
# https origin is ever neutralized.


def test_auth_origin_status_about_blank_neutral() -> None:
    # A blank start page alone must not disqualify bootstrap.
    assert auth_origin_status(("about:blank",)) is AuthOriginStatus.NO_ACTIVE_PAGE
    # about:blank alongside chrome://newtab is still neutral.
    assert (
        auth_origin_status(("about:blank", "chrome://newtab"))
        is AuthOriginStatus.NO_ACTIVE_PAGE
    )


def test_auth_origin_status_chrome_newtab_neutral() -> None:
    # Core newtab and harmless variants are neutral.
    assert auth_origin_status(("chrome://newtab",)) is AuthOriginStatus.NO_ACTIVE_PAGE
    assert (
        auth_origin_status(("chrome://newtab/",)) is AuthOriginStatus.NO_ACTIVE_PAGE
    )
    assert (
        auth_origin_status(("chrome://newtab/?something",))
        is AuthOriginStatus.NO_ACTIVE_PAGE
    )


def test_auth_origin_status_neutral_with_approved_login_allowed() -> None:
    # Neutral placeholders do not poison an otherwise approved context.
    assert (
        auth_origin_status(
            ("about:blank", "chrome://newtab", "https://login.microsoftonline.com/kmsi")
        )
        is AuthOriginStatus.APPROVED_AUTH_ORIGIN
    )
    # Approved auth origin alone still allowed (unchanged behavior).
    assert (
        auth_origin_status(("https://login.microsoftonline.com/kmsi",))
        is AuthOriginStatus.APPROVED_AUTH_ORIGIN
    )


def test_auth_origin_status_example_com_denied() -> None:
    # Arbitrary web origins remain denied even next to a neutral page.
    assert (
        auth_origin_status(("about:blank", "https://example.com/"))
        is AuthOriginStatus.NON_APPROVED_ORIGIN
    )
    assert (
        auth_origin_status(("chrome://newtab", "https://evil.example.com/"))
        is AuthOriginStatus.NON_APPROVED_ORIGIN
    )


def test_guard_auth_start_allowed_with_neutral_origin_pages() -> None:
    # End-to-end tie: when the live context is neutral placeholders plus an
    # approved Microsoft login origin, the bootstrap guard permits auth_start
    # (all other conditions hold). This exercises the neutral-origin fix in the
    # real guard decision path, not just auth_origin_status.
    def approved_provider() -> bool:
        return auth_origin_status(
            ("about:blank", "https://login.microsoftonline.com/kmsi")
        ) is AuthOriginStatus.APPROVED_AUTH_ORIGIN

    guard = AuthBootstrapGuard(
        browser_started_provider=lambda: True,
        dedicated_profile_provider=lambda: True,
        approved_auth_origin_provider=approved_provider,
        auth_attested_provider=lambda: False,
        strict_live_guard=lambda _op: None,
    )
    guard.guard("auth_start")  # must not raise
    guard.guard("auth_status")  # must not raise
    guard.guard("auth_resume")  # must not raise


def test_bootstrap_allowed_only_when_dedicated_profile_and_approved_origin() -> None:
    guard = _guard(started=True, dedicated=True, approved_origin=True)
    for op in ("auth_status", "auth_start", "auth_resume"):
        guard.guard(op)  # must not raise


def test_bootstrap_refuses_non_auth_operation() -> None:
    guard = _guard(started=True, dedicated=True, approved_origin=True)
    with pytest.raises(PolicyDenied):
        guard.guard("planner_plans_read")


def test_bootstrap_fails_closed_when_browser_not_started() -> None:
    guard = _guard(started=False, dedicated=True, approved_origin=True)
    with pytest.raises(WorkerUnavailable):
        guard.guard("auth_status")


def test_bootstrap_fails_closed_on_non_dedicated_profile() -> None:
    guard = _guard(started=True, dedicated=False, approved_origin=True)
    with pytest.raises(PolicyDenied):
        guard.guard("auth_status")


def test_bootstrap_fails_closed_on_wrong_origin() -> None:
    guard = _guard(started=True, dedicated=True, approved_origin=False)
    with pytest.raises(PolicyDenied):
        guard.guard("auth_status")


def test_bootstrap_defers_to_strict_guard_once_auth_attested() -> None:
    browser = _FakeBrowser(
        started=True, dedicated=True, approved_origin=True, auth_attested=True
    )
    guard = AuthBootstrapGuard(
        browser_started_provider=lambda: browser.started,
        dedicated_profile_provider=browser.is_dedicated_persistent_profile,
        approved_auth_origin_provider=browser.auth_origin_approved,
        auth_attested_provider=browser.common_auth_attested,
        strict_live_guard=browser.ensure_live_allowed,
    )
    with pytest.raises(UiContractUnattested):  # strict full-contract guard now applies
        guard.guard("auth_status")
    assert browser.strict_raised is True


@pytest.fixture()
def live_app():
    previous = {
        "PLANNER_MODE": os.environ.get("PLANNER_MODE"),
        "M365_MODE": os.environ.get("M365_MODE"),
    }
    os.environ["PLANNER_MODE"] = "live"
    os.environ["M365_MODE"] = "live"
    try:
        browser = _FakeBrowser(started=True, dedicated=True, approved_origin=True)
        yield create_app(browser=browser)
    finally:
        for name in ("PLANNER_MODE", "M365_MODE"):
            if previous[name] is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = previous[name]


async def test_live_auth_status_returns_no_secrets(live_app) -> None:
    transport = httpx.ASGITransport(app=live_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://worker") as client:
        response = await client.get("/auth/status")
        assert response.status_code == 200
        payload = response.json()
        assert payload == {"state": "UNKNOWN", "mode": "live"}
        flat = str(payload).lower()
        for forbidden in (
            "password",
            "token",
            "cookie",
            "bearer",
            "upn",
            "tenant",
            "mailbox",
            "url",
        ):
            assert forbidden not in flat


async def test_live_auth_start_and_resume_allowed_pre_attestation(live_app) -> None:
    transport = httpx.ASGITransport(app=live_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://worker") as client:
        assert (await client.get("/auth/start")).status_code == 200
        assert (await client.get("/auth/resume")).status_code == 200


async def test_live_planner_reads_still_blocked_pre_attestation(live_app) -> None:
    transport = httpx.ASGITransport(app=live_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://worker") as client:
        # Full-contract live_guard still blocks planner reads and account reads.
        assert (await client.get("/planner/plans")).status_code == 503
        assert (await client.get("/account/context")).status_code == 503
        assert (await client.get("/account/license")).status_code == 503


async def test_live_auth_blocked_on_wrong_origin() -> None:
    previous = {
        "PLANNER_MODE": os.environ.get("PLANNER_MODE"),
        "M365_MODE": os.environ.get("M365_MODE"),
    }
    os.environ["PLANNER_MODE"] = "live"
    os.environ["M365_MODE"] = "live"
    try:
        browser = _FakeBrowser(started=True, dedicated=True, approved_origin=False)
        app = create_app(browser=browser)
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://worker"
        ) as client:
            response = await client.get("/auth/status")
            assert response.status_code == 503
            assert response.json()["detail"]["error"] == "POLICY_DENIED"
    finally:
        for name in ("PLANNER_MODE", "M365_MODE"):
            if previous[name] is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = previous[name]


def test_operator_observation_binds_to_contract_set_digest_and_schema() -> None:
    contract_set = load_ui_contract_set()
    campaign = build_attestation_campaign(
        contract_set, AttestationLevel.DISCOVERY, fragment_ids=("common.auth",)
    )

    def fake_probe(selector_key: str, metadata) -> int:
        # Simulated sanitized structural probe: exactly one match for every
        # declared selector. This is a structural COUNT only; no content leaves.
        return 1

    observation = collect_structural_observation(
        "common.auth", AttestationLevel.DISCOVERY, live_probe=fake_probe
    )
    assert observation.campaign_id == campaign.campaign_id
    assert observation.contract_set_digest == campaign.contract_set_digest
    assert observation.source is ObservationSource.LIVE_UI
    for item in observation.selector_observations:
        assert item.result.value == "UNIQUE_MATCH"
        assert item.structural_digest.startswith("sha256:")


def test_mock_observation_cannot_promote_live_support() -> None:
    # End-to-end guard that MOCK evidence can never promote live support.
    contract_set = load_ui_contract_set()
    campaign = build_attestation_campaign(
        contract_set, AttestationLevel.DISCOVERY, fragment_ids=("common.auth",)
    )
    observation = AttestationObservation(
        campaign_id=campaign.campaign_id,
        contract_set_digest=campaign.contract_set_digest,
        fragment_id="common.auth",
        fragment_version="0.1.0",
        target_level=AttestationLevel.DISCOVERY,
        source=ObservationSource.MOCK,  # NOT live
        observed_at=datetime.datetime.now(datetime.UTC),
        selector_observations=tuple(
            SelectorObservation(
                selector_key=step.selector_key,
                result=SelectorObservationResult.UNIQUE_MATCH,
                structural_digest="sha256:"
                + hashlib.sha256(step.selector_key.encode()).hexdigest(),
            )
            for step in campaign.steps
        ),
    )
    decision = evaluate_attestation_observation(contract_set, observation)
    assert decision.state.value != "PASSED"
    assert "NON_LIVE_EVIDENCE_CANNOT_PROMOTE" in decision.reasons


def test_no_runtime_contract_mutation_in_collection_harness(tmp_path) -> None:
    # The collection harness writes an observation file but must never modify the
    # source contract JSON nor self-promote ATTESTED.
    before = load_ui_contract_set()

    def fake_probe(selector_key: str, metadata) -> int:
        return 1

    observation = collect_structural_observation(
        "common.auth", AttestationLevel.DISCOVERY, live_probe=fake_probe
    )
    out = tmp_path / "common.auth.observation.json"
    payload = observation.canonical_payload()

    out.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    assert out.exists()

    after = load_ui_contract_set()
    assert after.digest() == before.digest()
    assert not any(fragment.attested for fragment in after.fragments)
    assert not any(
        fragment.attestation_status == "ATTESTED" for fragment in after.fragments
    )


def test_auth_bootstrap_guard_module_has_no_generic_browser_tokens() -> None:
    import inspect

    from m365_browser_worker import auth_bootstrap

    source = inspect.getsource(auth_bootstrap).lower()
    for token in ("page.evaluate", "add_init_script", "goto", "navigate", "exec("):
        assert token not in source, token
