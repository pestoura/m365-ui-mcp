"""Application-neutral M365 MCP control-plane runtime."""

from .runtime import ToolRegistrar, build_control_plane

__all__ = ["ToolRegistrar", "build_control_plane"]
