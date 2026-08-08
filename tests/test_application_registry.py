"""CORE-007 closed Application Registry acceptance tests."""

from __future__ import annotations

import inspect
from typing import Any

import pytest

from m365_mcp.application_registry import (
    ApplicationKey,
    ApplicationRegistration,
    ApplicationRegistry,
    ApplicationState,
    default_application_registry,
)
from m365_mcp.config import Settings


def _registrar(calls: list[str], name: str):  # type: ignore[no-untyped-def]
    def register(server: Any, settings: Settings) -> None:
        del server, settings
        calls.append(name)

    return register


def test_default_registry_declares_planner_and_outlook_without_early_outlook_execution() -> None:
    registry = default_application_registry()

    assert registry.keys() == (ApplicationKey.PLANNER, ApplicationKey.OUTLOOK)
    assert registry.get(ApplicationKey.PLANNER).state is ApplicationState.ENABLED
    assert registry.get(ApplicationKey.PLANNER).registrar is not None
    assert registry.get(ApplicationKey.OUTLOOK).state is ApplicationState.RESERVED
    assert registry.get(ApplicationKey.OUTLOOK).registrar is None
    assert registry.snapshot() == (
        {
            "application": "planner",
            "state": "ENABLED",
            "capability_namespace": "planner",
        },
        {
            "application": "outlook",
            "state": "RESERVED",
            "capability_namespace": "outlook",
        },
    )


def test_only_enabled_registrars_are_projected(tmp_path: Any) -> None:
    calls: list[str] = []
    planner = _registrar(calls, "planner")
    registry = ApplicationRegistry(
        (
            ApplicationRegistration(
                ApplicationKey.PLANNER,
                ApplicationState.ENABLED,
                "planner",
                planner,
            ),
            ApplicationRegistration(
                ApplicationKey.OUTLOOK,
                ApplicationState.RESERVED,
                "outlook",
            ),
        )
    )

    registry.register_enabled_tools(
        object(),
        Settings(mode="mock", state_path=tmp_path / "state.sqlite3"),
    )
    assert calls == ["planner"]


def test_enabled_application_without_registrar_is_rejected() -> None:
    with pytest.raises(ValueError, match="requires a semantic registrar"):
        ApplicationRegistration(
            ApplicationKey.OUTLOOK,
            ApplicationState.ENABLED,
            "outlook",
        )


def test_reserved_application_cannot_smuggle_a_registrar() -> None:
    calls: list[str] = []
    with pytest.raises(ValueError, match="must not expose a registrar"):
        ApplicationRegistration(
            ApplicationKey.OUTLOOK,
            ApplicationState.RESERVED,
            "outlook",
            _registrar(calls, "outlook"),
        )


def test_duplicate_application_keys_are_rejected() -> None:
    calls: list[str] = []
    planner = _registrar(calls, "planner")
    registration = ApplicationRegistration(
        ApplicationKey.PLANNER,
        ApplicationState.ENABLED,
        "planner",
        planner,
    )
    with pytest.raises(ValueError, match="duplicate application registration"):
        ApplicationRegistry((registration, registration))


def test_registry_has_no_plugin_or_filesystem_self_registration() -> None:
    source = inspect.getsource(__import__("m365_mcp.application_registry", fromlist=["*"]))
    lowered = source.lower()
    assert "entry_points" not in lowered
    assert "pkgutil" not in lowered
    assert "filesystem" not in lowered.replace("filesystem discovery", "")
    assert "import_module" not in lowered
