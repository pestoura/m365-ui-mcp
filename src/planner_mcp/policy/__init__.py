"""Planner compatibility exports for the canonical M365 policy engine."""

from __future__ import annotations

from m365_mcp.policy import (
    READ_TOOLS,
    Decision,
    MetadataPolicyEngine,
    PolicyResult,
    evaluate,
)

__all__ = [
    "Decision",
    "MetadataPolicyEngine",
    "PolicyResult",
    "READ_TOOLS",
    "evaluate",
]
