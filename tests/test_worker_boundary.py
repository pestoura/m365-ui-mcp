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


def test_canonical_browser_profile_configuration(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_browser_env(monkeypatch)
    monkeypatch.setenv("M365_BROWSER_PROFILE_DIR", "/tmp/m365-profile")
    monkeypatch.setenv("M365_BROWSER_HEADLESS", "0")
    monkeypatch.setenv("M365_MODE", "mock")

    config = BrowserConfig.from_env()
    assert config.profile_dir == Path("/tmp/m365-profile")
    assert config.headless is False
    assert config.mode == "mock"


def test_legacy_browser_profile_configuration_remains_supported(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _clear_browser_env(monkeypatch)
    monkeypatch.setenv("PLANNER_BROWSER_PROFILE_DIR", "/tmp/planner-profile")
    monkeypatch.setenv("PLANNER_BROWSER_HEADLESS", "1")

    config = BrowserConfig.from_env()
    assert config.profile_dir == Path("/tmp/planner-profile")
    assert config.headless is True


def test_divergent_browser_aliases_fail_closed_without_values(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _clear_browser_env(monkeypatch)
    monkeypatch.setenv("M365_BROWSER_PROFILE_DIR", "/tmp/canonical-private")
    monkeypatch.setenv("PLANNER_BROWSER_PROFILE_DIR", "/tmp/legacy-private")

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
    assert "/tmp/canonical-private" not in rendered
    assert "/tmp/legacy-private" not in rendered
