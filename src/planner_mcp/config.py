"""Planner compatibility imports for canonical M365 runtime configuration."""

from __future__ import annotations

from m365_mcp.config import (
    CANONICAL_CONFIG_PREFIX,
    LEGACY_CONFIG_PREFIX,
    LEGACY_CONFIG_REMOVAL_VERSION,
    LEGACY_CONFIG_STATUS,
    Settings,
    configuration_metadata,
    load_settings,
    worker_bind_settings,
)

__all__ = [
    "CANONICAL_CONFIG_PREFIX",
    "LEGACY_CONFIG_PREFIX",
    "LEGACY_CONFIG_STATUS",
    "LEGACY_CONFIG_REMOVAL_VERSION",
    "Settings",
    "configuration_metadata",
    "load_settings",
    "worker_bind_settings",
]
