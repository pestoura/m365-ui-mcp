"""CORE-022 liveness/readiness separation tests."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from m365_browser_worker.browser import BrowserConfig, PersistentBrowser
from m365_browser_worker.readiness import ReadinessReason, evaluate_worker_readiness
from planner_browser_worker.app import create_app
from planner_mcp.auth import AuthState


class ReadyBrowser(PersistentBrowser):
    def __init__(self) -> None:
        super().__init__(BrowserConfig(profile_dir=Path.cwd() / ".ready-browser", mode="live"))

    @property
    def started(self) -> bool:
        return True

    async def start(self) -> None:
        return None

    async def stop(self) -> None:
        return None


def test_readiness_requires_all_live_subsystems() -> None:
    readiness = evaluate_worker_readiness(
        browser_started=False,
        profile_usable=False,
        auth_state=AuthState.UNKNOWN,
        ui_contract_attested=False,
        broker_viable=False,
        protocol_compatible=False,
        lock_viable=False,
    )
    assert readiness.ready is False
    assert readiness.reasons == (
        ReadinessReason.BROWSER_NOT_STARTED,
        ReadinessReason.PROFILE_UNAVAILABLE,
        ReadinessReason.AUTH_NOT_AUTHENTICATED,
        ReadinessReason.UI_CONTRACT_UNATTESTED,
        ReadinessReason.BROKER_UNAVAILABLE,
        ReadinessReason.PROTOCOL_INCOMPATIBLE,
        ReadinessReason.LOCK_UNAVAILABLE,
    )


def test_readiness_is_true_only_when_all_signals_are_positive() -> None:
    readiness = evaluate_worker_readiness(
        browser_started=True,
        profile_usable=True,
        auth_state=AuthState.AUTHENTICATED,
        ui_contract_attested=True,
        broker_viable=True,
        protocol_compatible=True,
        lock_viable=True,
    )
    assert readiness.ready is True
    assert readiness.reasons == ()


def test_liveness_and_legacy_health_do_not_overclaim_default_readiness() -> None:
    app = create_app()
    with TestClient(app) as client:
        live = client.get("/livez")
        ready = client.get("/readyz")
        health = client.get("/health")

    assert live.status_code == 200
    assert live.json()["alive"] is True
    assert "ready" not in live.json()
    assert ready.status_code == 503
    assert ready.json()["ready"] is False
    assert health.status_code == 200
    assert health.json()["live_ready"] is False
    reasons = set(ready.json()["reasons"])
    assert ReadinessReason.BROWSER_NOT_STARTED.value in reasons
    assert ReadinessReason.PROFILE_UNAVAILABLE.value in reasons
    assert ReadinessReason.BROKER_UNAVAILABLE.value in reasons
    assert ReadinessReason.PROTOCOL_INCOMPATIBLE.value in reasons
    assert ReadinessReason.LOCK_UNAVAILABLE.value in reasons


def test_readyz_and_legacy_health_use_same_proven_state(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PLANNER_MODE", "live")
    monkeypatch.setattr(
        "planner_browser_worker.app.load_status",
        lambda: SimpleNamespace(
            attested=True,
            version="0.1.0",
            contract_set_digest="sha256:test",
        ),
    )
    app = create_app(
        ReadyBrowser(),
        profile_viability_provider=lambda: True,
        auth_state_provider=lambda: AuthState.AUTHENTICATED,
        broker_viability_provider=lambda: True,
        protocol_compatibility_provider=lambda: True,
        lock_viability_provider=lambda: True,
    )

    with TestClient(app) as client:
        response = client.get("/readyz")
        health = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "ready": True,
        "target": "live_m365",
        "browser_started": True,
        "profile_usable": True,
        "auth_state": AuthState.AUTHENTICATED.value,
        "ui_contract_attested": True,
        "broker_viable": True,
        "protocol_compatible": True,
        "lock_viable": True,
        "reasons": [],
    }
    assert health.status_code == 200
    assert health.json()["live_ready"] is True


def test_single_negative_signal_keeps_readiness_failed() -> None:
    readiness = evaluate_worker_readiness(
        browser_started=True,
        profile_usable=True,
        auth_state=AuthState.AUTHENTICATED,
        ui_contract_attested=True,
        broker_viable=True,
        protocol_compatible=True,
        lock_viable=False,
    )
    assert readiness.ready is False
    assert readiness.reasons == (ReadinessReason.LOCK_UNAVAILABLE,)
