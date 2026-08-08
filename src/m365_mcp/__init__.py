"""Canonical Microsoft 365 MCP package identity.

The generic implementation is migrated behind this namespace in controlled CORE
blocks. Planner compatibility imports remain available during the transition.
"""

from .version import CONTRACT_VERSION, SCHEMA_VERSION, __version__

__all__ = ["__version__", "SCHEMA_VERSION", "CONTRACT_VERSION"]
