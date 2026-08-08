"""CORE-010 bounded tool profile/projection acceptance tests."""

from __future__ import annotations

import os
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest

from m365_mcp.config import Settings, load_settings
from m365_mcp.tool_profiles import ToolProfile, project_tool_definitions
from m365_mcp.tool_registry import MutationClass, ToolRegistry, default_tool_registry
from planner_mcp.errors import ConfigurationError
from planner_mcp.registration import register_planner_tools


class RecordingMcp:
    """Minimal FastMCP-like recorder for exposure tests."""

    def __init__(self) -> None:
        self.handlers: list[Any] = []

    def tool(self):  # type: ignore[no-untyped-def]
        def decorate(handler: Any) -> Any:
            self.handlers.append(handler)
            return handler

        return decorate


def _clear_config_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in tuple(os.environ):
        if name.upper().startswith(("M365_", "PLANNER_")):
            monkeypatch.delenv(name, raising=False)


def _settings(tmp_path: Path, profile: str = "full") -> Settings:
    return Settings(
        mode="mock",
        state_path=tmp_path / "state.sqlite3",
        tool_profile=profile,
    )


def test_current_registry_profile_counts_are_bounded() -> None:
    registry = default_tool_registry()
    assert len(project_tool_definitions(registry, ToolProfile.FULL)) == 17
    assert len(project_tool_definitions(registry, ToolProfile.PLANNER)) == 17
    assert len(project_tool_definitions(registry, ToolProfile.READ_ONLY)) == 17
    assert project_tool_definitions(registry, ToolProfile.OUTLOOK) == ()


def test_profiles_change_exposure_not_tool_governance() -> None:
    registry = default_tool_registry()
    original = registry.get("planner_health")
    projected = project_tool_definitions(registry, ToolProfile.READ_ONLY)[0]

    assert projected is original
    assert projected.mutation_class is MutationClass.READ
    assert projected.risk_class == original.risk_class
    assert projected.approval_requirement == original.approval_requirement
    assert projected.idempotency_semantics == original.idempotency_semantics


def test_read_only_projection_filters_mutations_without_rewriting_metadata() -> None:
    base = default_tool_registry().get("planner_health")
    update = replace(
        base,
        name="planner_synthetic_update",
        mutation_class=MutationClass.UPDATE,
        risk_class="SYNTHETIC_UPDATE",
        approval_requirement="required",
    )
    registry = ToolRegistry((base, update))

    assert tuple(item.name for item in project_tool_definitions(registry, "full")) == (
        "planner_health",
        "planner_synthetic_update",
    )
    assert tuple(item.name for item in project_tool_definitions(registry, "read-only")) == (
        "planner_health",
    )
    assert registry.get("planner_synthetic_update").approval_requirement == "required"


@pytest.mark.parametrize(
    ("profile", "expected_count"),
    [("full", 17), ("planner", 17), ("read-only", 17), ("outlook", 0)],
)
def test_planner_registration_respects_exposure_profile(
    tmp_path: Path,
    profile: str,
    expected_count: int,
) -> None:
    mcp = RecordingMcp()
    register_planner_tools(mcp, _settings(tmp_path, profile))
    assert len(mcp.handlers) == expected_count


def test_m365_tool_profile_is_canonical_typed_configuration(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _clear_config_env(monkeypatch)
    monkeypatch.setenv("M365_TOOL_PROFILE", "read-only")
    settings = load_settings()
    assert settings.tool_profile == "read-only"
    assert settings.public_summary()["tool_profile"] == "read-only"


def test_invalid_tool_profile_fails_closed_without_echoing_value(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _clear_config_env(monkeypatch)
    invalid = "not-a-profile"
    monkeypatch.setenv("M365_TOOL_PROFILE", invalid)

    with pytest.raises(ConfigurationError) as caught:
        load_settings()

    rendered = str(caught.value.to_dict())
    assert invalid not in rendered
    assert "literal_error" in rendered


def test_no_new_planner_alias_is_invented_for_new_m365_profile_setting(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _clear_config_env(monkeypatch)
    monkeypatch.setenv("PLANNER_TOOL_PROFILE", "outlook")
    assert load_settings().tool_profile == "full"
