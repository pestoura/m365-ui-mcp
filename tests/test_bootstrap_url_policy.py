"""URL allowlist / path-validation policy for the operator-only bootstrap target.

RED at first (no env-driven resolution / no path allowlist yet), GREEN after the
minimal change to ``bootstrap_navigation``.

The bootstrap target must be:
* env-overridable with a safe default, but
* validated by a closed policy: https only, host exactly ``planner.cloud.microsoft``,
  and only approved Planner Web paths (``/``, ``/webui/plan/...``,
  ``/webui/premiumplan/...``); anything else fails closed to the default.
"""

from __future__ import annotations

import importlib

from m365_browser_worker.bootstrap_navigation import (
    PLANNER_WEB_BOOTSTRAP_URL,
)
from m365_browser_worker.egress import EgressDecision


def _reload_with_env(monkeypatch, value):
    if value is None:
        monkeypatch.delenv("PLANNER_WEB_BOOTSTRAP_URL", raising=False)
    else:
        monkeypatch.setenv("PLANNER_WEB_BOOTSTRAP_URL", value)
    import m365_browser_worker.bootstrap_navigation as mod

    importlib.reload(mod)
    return mod


def test_default_constant_is_safe_planner_root() -> None:
    assert PLANNER_WEB_BOOTSTRAP_URL == "https://planner.cloud.microsoft/"


def test_validate_accepts_root_and_approved_paths(monkeypatch) -> None:
    mod = _reload_with_env(monkeypatch, None)
    for url in (
        "https://planner.cloud.microsoft/",
        "https://planner.cloud.microsoft/webui/plan/abc-123",
        "https://planner.cloud.microsoft/webui/premiumplan/50191d3f-5092-44c7-b719-e0efd56532aa/org/c5837053-931c-4251-a5a4-81b512a225e9/view/grid",
    ):
        decision = mod.validate_planner_web_bootstrap_url(url)
        assert decision.allowed is True, url
        assert decision == mod.evaluate_browser_egress(url)


def test_validate_rejects_wrong_host(monkeypatch) -> None:
    mod = _reload_with_env(monkeypatch, None)
    for url in (
        "https://planner.microsoft.com/",
        "https://example.com/webui/premiumplan/x",
        "https://login.microsoftonline.com/",
        "https://graph.microsoft.com/v1.0/me",
    ):
        decision = mod.validate_planner_web_bootstrap_url(url)
        assert decision.allowed is False, url


def test_validate_rejects_disallowed_path(monkeypatch) -> None:
    mod = _reload_with_env(monkeypatch, None)
    for url in (
        "https://planner.cloud.microsoft/landing",
        "https://planner.cloud.microsoft/tasks",
        "https://planner.cloud.microsoft/webui/foo/bar",
        "https://planner.cloud.microsoft/anything/else",
    ):
        decision = mod.validate_planner_web_bootstrap_url(url)
        assert decision.allowed is False, url


def test_validate_rejects_non_https(monkeypatch) -> None:
    mod = _reload_with_env(monkeypatch, None)
    decision = mod.validate_planner_web_bootstrap_url("http://planner.cloud.microsoft/")
    assert decision.allowed is False


def test_resolve_falls_back_to_default_when_unset(monkeypatch) -> None:
    mod = _reload_with_env(monkeypatch, None)
    assert mod.resolve_planner_web_bootstrap_url() == PLANNER_WEB_BOOTSTRAP_URL


def test_resolve_accepts_approved_premiumplan_deeplink(monkeypatch) -> None:
    deep = (
        "https://planner.cloud.microsoft/webui/premiumplan/"
        "50191d3f-5092-44c7-b719-e0efd56532aa/"
        "org/c5837053-931c-4251-a5a4-81b512a225e9/view/grid"
    )
    mod = _reload_with_env(monkeypatch, deep)
    assert mod.resolve_planner_web_bootstrap_url() == deep


def test_resolve_fails_closed_to_default_on_invalid_env(monkeypatch) -> None:
    mod = _reload_with_env(monkeypatch, "https://evil.example.com/premiumplan/x")
    assert mod.resolve_planner_web_bootstrap_url() == PLANNER_WEB_BOOTSTRAP_URL


def test_evaluate_bootstrap_target_uses_resolved_url(monkeypatch) -> None:
    deep = (
        "https://planner.cloud.microsoft/webui/premiumplan/"
        "50191d3f-5092-44c7-b719-e0efd56532aa/"
        "org/c5837053-931c-4251-a5a4-81b512a225e9/view/grid"
    )
    mod = _reload_with_env(monkeypatch, deep)
    decision = mod.evaluate_bootstrap_target()
    assert isinstance(decision, EgressDecision)
    assert decision.allowed is True
