"""planner-mcp — MCP server for Microsoft Planner Premium (browser-first).

This package is the specification foundation (BLOCK A). Runtime components are
implemented under backlog keys P-002 onward; see docs/backlog.md.
"""

from planner_mcp.version import CONTRACT_VERSION, PRODUCT_VERSION, SCHEMA_VERSION

__all__ = ["CONTRACT_VERSION", "PRODUCT_VERSION", "SCHEMA_VERSION"]
