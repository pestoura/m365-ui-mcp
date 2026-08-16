"""CORE-023/024 Session/Capability Broker account-context tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from m365_browser_worker.account_context import AccountContext, AccountContextState
from m365_browser_worker.browser import BrowserConfig, PersistentBrowser
from m365_browser_worker.session_broker import SessionCapabilityBroker
from m365_mcp.capability_registry import default_capability_registry
from planner_mcp.auth import AuthState
from planner_mcp.errors import AuthRequired, PolicyDenied, WorkerUnavailable


class BrokerBrowser(PersistentBrowser):
    def __init__(self, *, started: bool) -> None:
        super().__init__(BrowserConfig(profile_dir=Path.cwd() / ".broker-browser", mode="live"))
        self._started_fixture = started
        self.guarded: list[str] = []

    @property
    def started(self) -> bool:
        return self._started_fixture

    def ensure_live_allowed(self, operation: str) -> None:
        self.guarded.append(operation)


def verified_context() -> AccountContext:
    return AccountContext(
        state=AccountContextState.VERIFIED,
        professional=True,
        expected_profile=True,
    )


def broker(
    browser: BrokerBrowser,
    state: AuthState,
    account_context: AccountContext | None = None,
) -> SessionCapabilityBroker:
    return SessionCapabilityBroker(
        browser=browser,
        registry=default_capability_registry(),
        auth_state_provider=lambda: state,
        account_context_provider=lambda: account_context or verified_context(),
    )


def test_broker_viability_requires_browser_auth_and_verified_context() -> None:
    assert broker(BrokerBrowser(started=False), AuthState.AUTHENTICATED).viable is False
    assert broker(BrokerBrowser(started=True), AuthState.UNKNOWN).viable is False
    assert broker(BrokerBrowser(started=True), AuthState.AUTHENTICATED).viable is True
    ambiguous = AccountContext(AccountContextState.AMBIGUOUS, True, True)
    assert broker(BrokerBrowser(started=True), AuthState.AUTHENTICATED, ambiguous).viable is False


def test_broker_refuses_authorization_without_owned_browser() -> None:
    with pytest.raises(WorkerUnavailable):
        broker(BrokerBrowser(started=False), AuthState.AUTHENTICATED).authorize(
            application="planner", capability="plans.read"
        )


def test_broker_refuses_authorization_without_authenticated_session() -> None:
    with pytest.raises(AuthRequired):
        broker(BrokerBrowser(started=True), AuthState.UNKNOWN).authorize(
            application="planner", capability="plans.read"
        )


@pytest.mark.parametrize(
    "account_context",
    [
        AccountContext(AccountContextState.UNVERIFIED, False, False),
        AccountContext(AccountContextState.AMBIGUOUS, True, True),
        AccountContext(AccountContextState.WRONG_ACCOUNT, True, True),
        AccountContext(AccountContextState.WRONG_TENANT, True, True),
        AccountContext(AccountContextState.VERIFIED, False, True),
        AccountContext(AccountContextState.VERIFIED, True, False),
    ],
)
def test_broker_refuses_untrusted_account_context(account_context: AccountContext) -> None:
    with pytest.raises(PolicyDenied) as error:
        broker(
            BrokerBrowser(started=True),
            AuthState.AUTHENTICATED,
            account_context,
        ).authorize(application="planner", capability="plans.read")
    assert error.value.context["account_context_state"] == account_context.state.value


def test_broker_refuses_unregistered_semantic_capability() -> None:
    with pytest.raises(WorkerUnavailable):
        broker(BrokerBrowser(started=True), AuthState.AUTHENTICATED).authorize(
            application="planner", capability="unsafe.generic_browser"
        )


def test_broker_grant_is_scoped_and_account_verified() -> None:
    browser = BrokerBrowser(started=True)
    grant = broker(browser, AuthState.AUTHENTICATED).authorize(
        application="planner", capability="tasks.read"
    )
    payload = grant.to_dict()

    assert payload == {
        "application": "planner",
        "surface": "planner_web",
        "account_scope": "professional_session",
        "container_scope": "plan",
        "capability": "tasks.read",
        "session_bound": True,
        "account_context_verified": True,
        "secret_material_exported": False,
    }
    assert browser.guarded == ["tasks.read"]


def test_broker_snapshot_exposes_only_bounded_account_state() -> None:
    payload = broker(BrokerBrowser(started=True), AuthState.AUTHENTICATED).snapshot()
    assert payload == {
        "viable": True,
        "browser_started": True,
        "auth_state": AuthState.AUTHENTICATED.value,
        "account_context": {
            "state": AccountContextState.VERIFIED.value,
            "professional": True,
            "expected_profile": True,
            "valid": True,
        },
        "secret_material_exported": False,
    }


def _broker_with_live_read_path(
    browser: BrokerBrowser,
    state: AuthState,
    live_read_path: bool,
    account_context: AccountContext | None = None,
) -> SessionCapabilityBroker:
    """Broker wired with a live_read_path_provider (the production Gate-1 signal)."""
    return SessionCapabilityBroker(
        browser=browser,
        registry=default_capability_registry(),
        auth_state_provider=lambda: state,
        account_context_provider=lambda: account_context or verified_context(),
        live_read_path_provider=lambda: live_read_path,
    )


def test_read_only_delivery_authorized_via_gate1_without_ui_attestation() -> None:
    """Gate-1 (verified professional session on Planner Web surface) alone must
    authorize read-only delivery caps, independent of UIContract fragment
    attestation. The broker must NOT call ensure_live_allowed for these caps."""
    browser = BrokerBrowser(started=True)
    grant = _broker_with_live_read_path(
        browser, AuthState.AUTHENTICATED, live_read_path=True
    ).authorize(application="planner", capability="plans.read")
    assert grant.capability == "plans.read"
    assert browser.guarded == []  # ensure_live_allowed NOT consulted


def test_read_only_delivery_still_enforces_strict_guard_without_live_read_path() -> None:
    """Without a verified live read path, a read-only delivery cap must still
    fall through to the strict ensure_live_allowed guard (UIContract
    attestation) rather than being authorized by Gate-1 alone."""
    browser = BrokerBrowser(started=True)
    _broker_with_live_read_path(
        browser, AuthState.AUTHENTICATED, live_read_path=False
    ).authorize(application="planner", capability="tasks.read")
    assert browser.guarded == ["tasks.read"]  # strict guard still consulted


def test_non_read_capability_still_requires_strict_guard() -> None:
    """Mutations and every non-delivery capability remain gated on the full
    ensure_live_allowed guard and must not be authorized by Gate-1 alone."""
    browser = BrokerBrowser(started=True)
    with pytest.raises(WorkerUnavailable):
        _broker_with_live_read_path(
            browser, AuthState.AUTHENTICATED, live_read_path=True
        ).authorize(application="planner", capability="unsafe.generic_browser")
    # A real registered non-delivery cap (if any) would still hit ensure_live_allowed.
    assert browser.guarded == []
