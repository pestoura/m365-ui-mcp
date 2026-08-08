"""CORE-029 worker protocol version negotiation tests."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from m365_browser_worker.browser import BrowserConfig, PersistentBrowser
from m365_browser_worker.protocol_negotiation import ProtocolNegotiator
from planner_browser_worker.app import create_app
from planner_mcp.auth import AuthState


class ReadyBrowser(PersistentBrowser):
    def __init__(self, profile_dir: Path) -> None:
        super().__init__(BrowserConfig(profile_dir=profile_dir, mode="live"))

    @property
    def started(self) -> bool:
        return True

    async def start(self) -> None:
        return None

    async def stop(self) -> None:
        return None


def test_negotiator_is_fail_closed_until_explicit_compatible_handshake() -> None:
    negotiator = ProtocolNegotiator()
    assert negotiator.compatible is False
    assert negotiator.negotiated_version is None

    incompatible = negotiator.negotiate(["2"])
    assert incompatible.compatible is False
    assert negotiator.compatible is False

    compatible = negotiator.negotiate(["1", "2"])
    assert compatible.compatible is True
    assert compatible.negotiated_version == "1"
    assert negotiator.compatible is True

    negotiator.reset()
    assert negotiator.compatible is False


def test_handshake_promotes_only_protocol_readiness_signal(
    tmp_path: Path,
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
    negotiator = ProtocolNegotiator()
    app = create_app(
        ReadyBrowser(tmp_path / "profile"),
        profile_viability_provider=lambda: True,
        auth_state_provider=lambda: AuthState.AUTHENTICATED,
        broker_viability_provider=lambda: True,
        lock_viability_provider=lambda: True,
        protocol_negotiator=negotiator,
    )

    with TestClient(app) as client:
        before = client.get("/readyz")
        handshake = client.post(
            "/protocol/negotiate",
            json={"supported_versions": ["1"]},
        )
        after = client.get("/readyz")

    assert before.status_code == 503
    assert before.json()["protocol_compatible"] is False
    assert handshake.status_code == 200
    assert handshake.json() == {
        "compatible": True,
        "negotiated_version": "1",
        "worker_supported_versions": ["1"],
    }
    assert after.status_code == 200
    assert after.json()["protocol_compatible"] is True


def test_incompatible_renegotiation_revokes_protocol_readiness(
    tmp_path: Path,
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
        ReadyBrowser(tmp_path / "profile"),
        profile_viability_provider=lambda: True,
        auth_state_provider=lambda: AuthState.AUTHENTICATED,
        broker_viability_provider=lambda: True,
        lock_viability_provider=lambda: True,
    )

    with TestClient(app) as client:
        accepted = client.post("/protocol/negotiate", json={"supported_versions": ["1"]})
        ready = client.get("/readyz")
        rejected = client.post("/protocol/negotiate", json={"supported_versions": ["2"]})
        revoked = client.get("/readyz")

    assert accepted.json()["compatible"] is True
    assert ready.status_code == 200
    assert rejected.json()["compatible"] is False
    assert rejected.json()["negotiated_version"] is None
    assert revoked.status_code == 503
    assert revoked.json()["protocol_compatible"] is False


def test_protocol_status_and_handshake_are_bounded() -> None:
    app = create_app()
    with TestClient(app) as client:
        status = client.get("/protocol")
        extra = client.post(
            "/protocol/negotiate",
            json={"supported_versions": ["1"], "url": "https://example.com/"},
        )
        malformed = client.post(
            "/protocol/negotiate",
            json={"supported_versions": ["latest"]},
        )

    assert status.status_code == 200
    assert status.json() == {
        "compatible": False,
        "negotiated_version": None,
        "supported_versions": ["1"],
    }
    assert extra.status_code == 422
    assert malformed.status_code == 422
