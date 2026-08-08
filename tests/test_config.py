"""P-003 typed, fail-closed configuration tests."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
from pydantic import ValidationError

from planner_mcp.config import Settings, load_settings
from planner_mcp.errors import ConfigurationError


def _clear_planner_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in tuple(os.environ):
        if name.upper().startswith("PLANNER_"):
            monkeypatch.delenv(name, raising=False)


def test_mock_settings_use_safe_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_planner_env(monkeypatch)
    settings = load_settings()
    assert settings.mode == "mock"
    assert settings.allow_mutations is False
    assert settings.require_ui_contract_attestation is True
    assert settings.is_mock is True


def test_live_mode_requires_explicit_worker_and_state(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_planner_env(monkeypatch)
    monkeypatch.setenv("PLANNER_MODE", "live")

    with pytest.raises(ConfigurationError) as caught:
        load_settings()

    payload = caught.value.to_dict()
    assert payload["error"] == "CONFIG_INVALID"
    assert payload["context"] == {
        "missing": ["PLANNER_WORKER_URL", "PLANNER_STATE_PATH"]
    }


def test_valid_live_settings_require_ui_attestation(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _clear_planner_env(monkeypatch)
    monkeypatch.setenv("PLANNER_MODE", "live")
    monkeypatch.setenv("PLANNER_WORKER_URL", "http://worker.internal:8090")
    monkeypatch.setenv("PLANNER_STATE_PATH", str(tmp_path / "state.sqlite3"))

    settings = load_settings()
    assert settings.is_live is True
    assert settings.worker_base_url == "http://worker.internal:8090"
    assert settings.require_ui_contract_attestation is True

    with pytest.raises(ValidationError):
        Settings(
            mode="live",
            worker_base_url="http://worker.internal:8090",
            state_path=tmp_path / "state.sqlite3",
            require_ui_contract_attestation=False,
        )


def test_public_mutations_cannot_be_enabled(tmp_path: Path) -> None:
    with pytest.raises(ValidationError):
        Settings(mode="mock", state_path=tmp_path / "state.sqlite3", allow_mutations=True)


def test_credential_shaped_planner_env_is_rejected_without_value_leak(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _clear_planner_env(monkeypatch)
    test_marker = "not-a-real-credential-value"
    monkeypatch.setenv("PLANNER_API_TOKEN", test_marker)

    with pytest.raises(ConfigurationError) as caught:
        load_settings()

    rendered = json.dumps(caught.value.to_dict(), sort_keys=True)
    assert "PLANNER_API_TOKEN" in rendered
    assert test_marker not in rendered


def test_invalid_environment_value_is_not_echoed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _clear_planner_env(monkeypatch)
    raw_value = "definitely-not-a-port"
    monkeypatch.setenv("PLANNER_MCP_PORT", raw_value)

    with pytest.raises(ConfigurationError) as caught:
        load_settings()

    rendered = json.dumps(caught.value.to_dict(), sort_keys=True)
    assert caught.value.code == "CONFIG_INVALID"
    assert raw_value not in rendered
    assert "int_parsing" in rendered


def test_settings_display_redacts_paths_and_urls(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _clear_planner_env(monkeypatch)
    worker_url = "http://private-worker.example:8090"
    state_path = tmp_path / "private-state.sqlite3"
    settings = Settings(
        mode="mock",
        worker_base_url=worker_url,
        state_path=state_path,
    )

    summary = settings.public_summary()
    rendered = repr(settings)
    assert summary["worker_base_url"] == "[REDACTED]"
    assert summary["state_path"] == "[REDACTED]"
    assert summary["host"] == "[REDACTED]"
    assert worker_url not in rendered
    assert str(state_path) not in rendered


def test_startup_exits_nonzero_with_typed_sanitized_error() -> None:
    env = {
        key: value
        for key, value in os.environ.items()
        if not key.upper().startswith("PLANNER_")
    }
    env["PLANNER_MODE"] = "live"

    completed = subprocess.run(
        [sys.executable, "-m", "planner_mcp"],
        env=env,
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )

    assert completed.returncode == 2
    payload = json.loads(completed.stderr.strip())
    assert payload["error"] == "CONFIG_INVALID"
    assert payload["context"]["missing"] == ["PLANNER_WORKER_URL", "PLANNER_STATE_PATH"]
    assert "password" not in completed.stderr.lower()
    assert "token" not in completed.stderr.lower()
