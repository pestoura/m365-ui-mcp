"""Planner compatibility import for canonical M365 version constants."""

from __future__ import annotations

from m365_mcp.version import (
    CONTRACT_VERSION,
    PRODUCT_VERSION,
    SCHEMA_VERSION,
    TOOL_CATALOG_VERSION,
    UI_CONTRACT_VERSION,
    __version__,
)

__all__ = [
    "PRODUCT_VERSION",
    "CONTRACT_VERSION",
    "SCHEMA_VERSION",
    "UI_CONTRACT_VERSION",
    "TOOL_CATALOG_VERSION",
    "__version__",
]
