"""CORE-009 metadata-driven semantic registration acceptance tests."""

from __future__ import annotations

import inspect
from pathlib import Path
from typing import Any

from m365_mcp.config import Settings
from m365_mcp.tool_registry import default_tool_registry
from planner_mcp.registration import _planner_bindings, register_planner_tools
from planner_mcp.tools import PlannerTools


class RecordingMcp:
    """Minimal FastMCP-like recorder for registration semantics."""

    def __init__(self) -> None:
        self.handlers: list[Any] = []

    def tool(self):  # type: ignore[no-untyped-def]
        def decorate(handler: Any) -> Any:
            self.handlers.append(handler)
            return handler

        return decorate


def _settings(tmp_path: Path) -> Settings:
    return Settings(mode="mock", state_path=tmp_path / "state.sqlite3")


def test_registry_drives_exact_public_registration_order(tmp_path: Path) -> None:
    mcp = RecordingMcp()
    register_planner_tools(mcp, _settings(tmp_path))

    expected = tuple(
        definition.name
        for definition in default_tool_registry().by_application("planner")
    )
    assert tuple(handler.__name__ for handler in mcp.handlers) == expected
    assert len(mcp.handlers) == 17


def test_all_projected_handlers_are_explicit_typed_functions(tmp_path: Path) -> None:
    bindings = _planner_bindings(PlannerTools(_settings(tmp_path)))
    registry = default_tool_registry()

    assert set(bindings) == set(registry.names())
    for name, handler in bindings.items():
        signature = inspect.signature(handler)
        assert all(
            parameter.kind
            not in {inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD}
            for parameter in signature.parameters.values()
        )
        required_schema_fields = tuple(registry.get(name).input_schema["required"])
        assert tuple(signature.parameters) == required_schema_fields


def test_registration_source_has_no_generic_executor_or_browser_primitives() -> None:
    source = inspect.getsource(__import__("planner_mcp.registration", fromlist=["*"]))
    lowered = source.lower()
    forbidden = (
        "browser_exec",
        "javascript",
        "xpath",
        "eval(",
        "exec(",
        "subprocess",
        "os.system",
    )
    assert all(token not in lowered for token in forbidden)
