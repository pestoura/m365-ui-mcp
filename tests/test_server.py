"""FastMCP server registration tests."""

from __future__ import annotations

from typing import Any

import pytest

from planner_mcp.config import Settings
from planner_mcp.server import build_server
from planner_mcp.tools import TOOL_NAMES


async def _registered_names(server: Any) -> set[str]:
    for attr in ("_list_tools", "get_tools", "list_tools"):
        candidate = getattr(server, attr, None)
        if candidate is None:
            continue
        result = await candidate()
        if isinstance(result, dict):
            return set(result)
        return {tool.name for tool in result}
    pytest.skip("FastMCP tool introspection API not available")


async def test_all_17_tools_registered(tmp_path: Any) -> None:
    server = build_server(Settings(mode="mock", state_path=tmp_path / "s.sqlite3"))
    assert await _registered_names(server) == set(TOOL_NAMES)
