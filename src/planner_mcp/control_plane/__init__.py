"""Public control-plane package boundary.

The implementation remains in :mod:`planner_mcp.server` during the 0.1.0
foundation, while this package provides the stable architectural namespace
required by P-002.
"""

from ..server import build_server, run

__all__ = ["build_server", "run"]
