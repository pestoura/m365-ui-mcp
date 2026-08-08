"""CORE-005 application-neutral control-plane boundary tests."""

from __future__ import annotations

import ast
import inspect
from typing import Any

from m365_mcp.config import Settings
from m365_mcp.control_plane import build_control_plane
from m365_mcp.control_plane import runtime as control_plane_runtime
from m365_mcp.server import build_server as m365_build_server
from planner_mcp.server import build_server as planner_build_server
from planner_mcp.tools import TOOL_NAMES


def test_generic_control_plane_has_no_planner_imports() -> None:
    tree = ast.parse(inspect.getsource(control_plane_runtime))
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)
    assert not any(name == "planner_mcp" or name.startswith("planner_mcp.") for name in imported)


def test_generic_control_plane_uses_injected_registrar(tmp_path: Any) -> None:
    seen: list[tuple[Any, Settings]] = []
    settings = Settings(mode="mock", state_path=tmp_path / "state.sqlite3")

    def register(server: Any, received: Settings) -> None:
        seen.append((server, received))

    server = build_control_plane(
        settings,
        name="boundary-test",
        version="0.1.0",
        register_tools=register,
    )

    assert seen == [(server, settings)]


def test_planner_server_is_compatibility_import_of_canonical_server() -> None:
    assert planner_build_server is m365_build_server


def test_current_projection_remains_exactly_planner_baseline() -> None:
    assert len(TOOL_NAMES) == 17
    assert all(name.startswith("planner_") for name in TOOL_NAMES)
