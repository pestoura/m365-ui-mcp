"""CORE-004 typed canonical configuration and compatibility tests."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
from pydantic import ValidationError

from m365_mcp.config import (
    LEGACY_CONFIG_REMOVAL_VERSION,
    LEGACY_CONFIG_STATUS,
    Settings,
    configuration_metadata,
    load_settings,
    worker_bind_settings,
)
from planner_mcp.config import Settings as PlannerSettings
from planner_mcp.config import load_settings as planner_load_settings
from planner_mcp.errors import ConfigurationError


def _clear_config_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in tuple(os.environ):
        if name.upper().startswith(("M365_", "PLANNER_")):
            monkeypatch.delenv(name, raising=False)


def _clean_subprocess_env() -> dict[str, str]:
    return {
        key: value
        for key, value in os.environ.items()
        if not key.upper().startswith(("M365_", "PLANNER_"))
    }


def test_mock_settings_use_safe_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_config_env(monkeypatch)
    settings = load_settings()
    assert settings.mode == "mock"
    assert settings.allow_mutations is False
    assert settings.require_ui_contract_attestation is True
    assert settings.is_mock is True


def test_m365_live_mode_uses_canonical_missing_names(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_config_env(monkeypatch)
    monkeypatch.setenv("M365_MODE", "live")

    with pytest.raises(ConfigurationError) as caught:
        load_settings()

    assert caught.value.to_dict()["context"] == {
        "missing": ["M365_WORKER_URL", "M365_STATE_PATH"]
    }


def test_legacy_live_mode_preserves_legacy_missing_names(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_config_env(monkeypatch)
    monkeypatch.setenv("PLANNER_MODE", "live")

    with pytest.raises(ConfigurationError) as caught:
        load_settings()

    assert caught.value.to_dict()["context"] == {
        "missing": ["PLANNER_WORKER_URL", "PLANNER_STATE_PATH"]
    }


def test_valid_canonical_live_settings(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _clear_config_env(monkeypatch)
    monkeypatch.setenv("M365_MODE", "live")
    monkeypatch.setenv("M365_WORKER_URL", "http://worker.internal:8090")
    monkeypatch.setenv("M365_STATE_PATH", str(tmp_path / "state.sqlite3"))

    settings = load_settings()
    assert settings.is_live is True
    assert settings.worker_base_url == "http://worker.internal:8090"
    assert settings.require_ui_contract_attestation is True


def test_valid_legacy_live_settings_remain_supported(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _clear_config_env(monkeypatch)
    monkeypatch.setenv("PLANNER_MODE", "live")
    monkeypatch.setenv("PLANNER_WORKER_URL", "http://worker.internal:8090")
    monkeypatch.setenv("PLANNER_STATE_PATH", str(tmp_path / "state.sqlite3"))

    settings = planner_load_settings()
    assert settings.is_live is True
    assert settings.worker_base_url == "http://worker.internal:8090"
    assert PlannerSettings is Settings


def test_matching_dual_definitions_are_accepted(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_config_env(monkeypatch)
    monkeypatch.setenv("M365_MCP_PORT", "8081")
    monkeypatch.setenv("PLANNER_MCP_PORT", "8081")
    assert load_settings().port == 8081


def test_divergent_dual_definitions_fail_closed_without_value_leak(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _clear_config_env(monkeypatch)
    canonical_value = "8081"
    legacy_value = "8082"
    monkeypatch.setenv("M365_MCP_PORT", canonical_value)
    monkeypatch.setenv("PLANNER_MCP_PORT", legacy_value)

    with pytest.raises(ConfigurationError) as caught:
        load_settings()

    rendered = json.dumps(caught.value.to_dict(), sort_keys=True)
    assert caught.value.context == {
        "conflicts": [{"canonical": "M365_MCP_PORT", "legacy": "PLANNER_MCP_PORT"}]
    }
    assert canonical_value not in rendered
    assert legacy_value not in rendered


def test_public_mutations_cannot_be_enabled(tmp_path: Path) -> None:
    with pytest.raises(ValidationError):
        Settings(mode="mock", state_path=tmp_path / "state.sqlite3", allow_mutations=True)


@pytest.mark.parametrize("name", ["M365_API_TOKEN", "PLANNER_API_TOKEN"])
def test_credential_shaped_env_is_rejected_without_value_leak(
    monkeypatch: pytest.MonkeyPatch,
    name: str,
) -> None:
    _clear_config_env(monkeypatch)
    marker = "not-a-real-credential-value"
    monkeypatch.setenv(name, marker)

    with pytest.raises(ConfigurationError) as caught:
        load_settings()

    rendered = json.dumps(caught.value.to_dict(), sort_keys=True)
    assert name in rendered
    assert marker not in rendered


def test_invalid_canonical_environment_value_is_not_echoed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _clear_config_env(monkeypatch)
    raw_value = "definitely-not-a-port"
    monkeypatch.setenv("M365_MCP_PORT", raw_value)

    with pytest.raises(ConfigurationError) as caught:
        load_settings()

    rendered = json.dumps(caught.value.to_dict(), sort_keys=True)
    assert caught.value.code == "CONFIG_INVALID"
    assert raw_value not in rendered
    assert "int_parsing" in rendered


def test_settings_display_redacts_paths_and_urls(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _clear_config_env(monkeypatch)
    worker_url = "http://private-worker.example:8090"
    state_path = tmp_path / "private-state.sqlite3"
    settings = Settings(mode="mock", worker_base_url=worker_url, state_path=state_path)

    summary = settings.public_summary()
    rendered = repr(settings)
    assert summary["worker_base_url"] == "[REDACTED]"
    assert summary["state_path"] == "[REDACTED]"
    assert summary["host"] == "[REDACTED]"
    assert worker_url not in rendered
    assert str(state_path) not in rendered


def test_alias_metadata_is_explicit_and_bounded() -> None:
    metadata = configuration_metadata()
    assert metadata["canonical_namespace"] == "M365_"
    assert metadata["legacy_namespace"] == "PLANNER_"
    assert LEGACY_CONFIG_STATUS == "DEPRECATED_ALIAS"
    assert LEGACY_CONFIG_REMOVAL_VERSION == "2.0.0"
    aliases = metadata["aliases"]
    assert isinstance(aliases, dict)
    assert aliases["M365_WORKER_URL"] == "PLANNER_WORKER_URL"


def test_worker_bind_uses_canonical_and_legacy_aliases() -> None:
    assert worker_bind_settings({"M365_WORKER_HOST": "127.0.0.2", "M365_WORKER_PORT": "8091"}) == (
        "127.0.0.2",
        8091,
    )
    assert worker_bind_settings(
        {"PLANNER_WORKER_HOST": "127.0.0.3", "PLANNER_WORKER_PORT": "8092"}
    ) == ("127.0.0.3", 8092)


def test_worker_bind_rejects_divergent_aliases_without_values() -> None:
    with pytest.raises(ConfigurationError) as caught:
        worker_bind_settings({"M365_WORKER_PORT": "8091", "PLANNER_WORKER_PORT": "8092"})
    assert caught.value.context == {
        "conflicts": [{"canonical": "M365_WORKER_PORT", "legacy": "PLANNER_WORKER_PORT"}]
    }


def test_m365_startup_exits_nonzero_with_canonical_typed_error() -> None:
    env = _clean_subprocess_env()
    env["M365_MODE"] = "live"

    completed = subprocess.run(
        [sys.executable, "-m", "m365_mcp"],
        env=env,
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )

    assert completed.returncode == 2
    payload = json.loads(completed.stderr.strip())
    assert payload["error"] == "CONFIG_INVALID"
    assert payload["context"]["missing"] == ["M365_WORKER_URL", "M365_STATE_PATH"]
    assert "password" not in completed.stderr.lower()
    assert "token" not in completed.stderr.lower()


def test_planner_startup_retains_legacy_typed_error() -> None:
    env = _clean_subprocess_env()
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
    assert payload["context"]["missing"] == [
        "PLANNER_WORKER_URL",
        "PLANNER_STATE_PATH",
    ]
