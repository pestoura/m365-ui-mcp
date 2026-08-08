"""Configuration. Secrets are never read into MCP state."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


def _b(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    """Runtime settings for the control plane."""

    mode: str = field(default_factory=lambda: os.getenv("PLANNER_MODE", "mock"))
    host: str = field(default_factory=lambda: os.getenv("PLANNER_MCP_HOST", "127.0.0.1"))
    port: int = field(default_factory=lambda: int(os.getenv("PLANNER_MCP_PORT", "8080")))
    worker_base_url: str = field(
        default_factory=lambda: os.getenv("PLANNER_WORKER_URL", "http://127.0.0.1:8090")
    )
    state_path: Path = field(
        default_factory=lambda: Path(
            os.getenv("PLANNER_STATE_PATH", "/var/lib/planner-mcp/state.sqlite3")
        )
    )
    request_timeout_s: float = field(
        default_factory=lambda: float(os.getenv("PLANNER_REQUEST_TIMEOUT_S", "30"))
    )
    allow_mutations: bool = field(default_factory=lambda: _b("PLANNER_ALLOW_MUTATIONS", False))
    require_ui_contract_attestation: bool = field(
        default_factory=lambda: _b("PLANNER_REQUIRE_UI_ATTESTATION", True)
    )
    log_level: str = field(default_factory=lambda: os.getenv("PLANNER_LOG_LEVEL", "INFO"))

    @property
    def is_mock(self) -> bool:
        return self.mode.lower() == "mock"

    @property
    def is_live(self) -> bool:
        return self.mode.lower() == "live"


def load_settings() -> Settings:
    """Load settings from the environment (fail-closed defaults)."""
    return Settings()
