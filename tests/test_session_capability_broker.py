"""CORE-023 Session/Capability Broker tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from m365_browser_worker.browser import BrowserConfig, PersistentBrowser
from m365_browser_worker.session_broker import SessionCapabilityBroker
from m365_mcp.capability_registry import default_capability_registry
from planner_mcp.auth import AuthState
from planner_mcp.errors import AuthRequired, WorkerUnavailable


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


def broker(browser: BrokerBrowser, state: AuthState) -> SessionCapabilityBroker:
    return SessionCapabilityBroker(
        browser=browser,
        registry=default_capability_registry(),
        auth_state_provider=lambda: state,
    )


def test_broker_viability_requires_browser_and_authenticated_session() -> None:
    assert broker(BrokerBrowser(started=False), AuthState.AUTHENTICATED).viable is False
    assert broker(BrokerBrowser(started=True), AuthState.UNKNOWN).viable is False
    assert broker(BrokerBrowser(started=True), AuthState.AUTHENTICATED).viable is True


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


def test_broker_refuses_unregistered_semantic_capability() -> None:
    with pytest.raises(WorkerUnavailable):
        broker(BrokerBrowser(started=True), AuthState.AUTHENTICATED).authorize(
            application="planner", capability="unsafe.generic_browser"
        )


def test_broker_grant_is_scoped_and_contains_no_secret_material() -> None:
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
        "secret_material_exported": False,
    }
    assert browser.guarded == ["tasks.read"]
    assert not ({"cookie", "cookies", "token", "tokens", "storage_state"} & set(payload))


def test_broker_snapshot_is_content_free() -> None:
    payload = broker(BrokerBrowser(started=True), AuthState.AUTHENTICATED).snapshot()
    assert payload == {
        "viable": True,
        "browser_started": True,
        "auth_state": AuthState.AUTHENTICATED.value,
        "secret_material_exported": False,
    }
