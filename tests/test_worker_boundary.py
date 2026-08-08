"""CORE-006 browser-worker boundary and Planner compatibility acceptance tests."""

from __future__ import annotations

import inspect
import os
from pathlib import Path

import pytest

from m365_browser_worker.browser import BrowserConfig, PersistentBrowser
from planner_browser_worker.browser import BrowserConfig as PlannerBrowserConfig
from planner_browser_worker.browser import PersistentBrowser as PlannerPersistentBrowser
from planner_mcp.errors import ConfigurationError


def _clear_browser_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in tuple(os.environ):
        if name.upper().startswith(("M365_", "PLANNER_")):
            monkeypatch.delenv(name, raising=False)


def test_planner_browser_lifecycle_is_exact_compatibility_import() -> None:
    assert PlannerBrowserConfig is BrowserConfig
    assert PlannerPersistentBrowser is PersistentBrowser


def test_canonical_worker_owns_browser_lifecycle_without_reverse_dependency() -> None:
    source = inspect.getsource(__import__("m365_browser_worker.browser", fromlist=["*"]))
    assert "planner_browser_worker" not in source
    assert "browser_exec" not in source
    assert "javascript" not in source.lower()
    assert "xpath" not in source.lower()


def test_canonical_browser_profile_configuration(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _clear_browser_env(monkeypatch)
    profile_dir = tmp_path / "m365-profile"
    monkeypatch.setenv("M365_BROWSER_PROFILE_DIR", str(profile_dir))
    monkeypatch.setenv("M365_BROWSER_HEADLESS", "0")
    monkeypatch.setenv("M365_MODE", "mock")

    config = BrowserConfig.from_env()
    assert config.profile_dir == profile_dir
    assert config.headless is False
    assert config.mode == "mock"


def test_legacy_browser_profile_configuration_remains_supported(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _clear_browser_env(monkeypatch)
    profile_dir = tmp_path / "planner-profile"
    monkeypatch.setenv("PLANNER_BROWSER_PROFILE_DIR", str(profile_dir))
    monkeypatch.setenv("PLANNER_BROWSER_HEADLESS", "1")

    config = BrowserConfig.from_env()
    assert config.profile_dir == profile_dir
    assert config.headless is True


def test_divergent_browser_aliases_fail_closed_without_values(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _clear_browser_env(monkeypatch)
    canonical_value = str(tmp_path / "canonical-private")
    legacy_value = str(tmp_path / "legacy-private")
    monkeypatch.setenv("M365_BROWSER_PROFILE_DIR", canonical_value)
    monkeypatch.setenv("PLANNER_BROWSER_PROFILE_DIR", legacy_value)

    with pytest.raises(ConfigurationError) as caught:
        BrowserConfig.from_env()

    assert caught.value.context == {
        "conflicts": [
            {
                "canonical": "M365_BROWSER_PROFILE_DIR",
                "legacy": "PLANNER_BROWSER_PROFILE_DIR",
            }
        ]
    }
    rendered = str(caught.value.to_dict())
    assert canonical_value not in rendered
    assert legacy_value not in rendered
