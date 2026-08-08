"""Canonical typed, fail-closed M365 runtime configuration.

`M365_*` is canonical. `PLANNER_*` remains a bounded compatibility alias until
its documented removal version. Divergent dual definitions are rejected rather
than silently resolved.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from pathlib import Path
from typing import Any, Literal
from urllib.parse import urlsplit

from pydantic import AliasChoices, Field, ValidationError, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from planner_mcp.errors import ConfigurationError

CANONICAL_CONFIG_PREFIX = "M365_"
LEGACY_CONFIG_PREFIX = "PLANNER_"
LEGACY_CONFIG_STATUS = "DEPRECATED_ALIAS"
LEGACY_CONFIG_REMOVAL_VERSION = "2.0.0"
_REDACTED = "[REDACTED]"

_CREDENTIAL_MARKERS = (
    "PASSWORD",
    "PASSWD",
    "TOKEN",
    "SECRET",
    "API_KEY",
    "APIKEY",
    "CREDENTIAL",
    "COOKIE",
    "PRIVATE_KEY",
    "ACCESS_KEY",
)

_CONFIG_ALIAS_PAIRS: tuple[tuple[str, str], ...] = (
    ("M365_MODE", "PLANNER_MODE"),
    ("M365_MCP_HOST", "PLANNER_MCP_HOST"),
    ("M365_MCP_PORT", "PLANNER_MCP_PORT"),
    ("M365_WORKER_URL", "PLANNER_WORKER_URL"),
    ("M365_STATE_PATH", "PLANNER_STATE_PATH"),
    ("M365_REQUEST_TIMEOUT_S", "PLANNER_REQUEST_TIMEOUT_S"),
    ("M365_ALLOW_MUTATIONS", "PLANNER_ALLOW_MUTATIONS"),
    ("M365_REQUIRE_UI_ATTESTATION", "PLANNER_REQUIRE_UI_ATTESTATION"),
    ("M365_LOG_LEVEL", "PLANNER_LOG_LEVEL"),
    ("M365_WORKER_HOST", "PLANNER_WORKER_HOST"),
    ("M365_WORKER_PORT", "PLANNER_WORKER_PORT"),
    ("M365_BROWSER_PROFILE_DIR", "PLANNER_BROWSER_PROFILE_DIR"),
    ("M365_BROWSER_HEADLESS", "PLANNER_BROWSER_HEADLESS"),
)

_LIVE_REQUIRED_PAIRS = (
    ("M365_WORKER_URL", "PLANNER_WORKER_URL"),
    ("M365_STATE_PATH", "PLANNER_STATE_PATH"),
)


def _normalized_environment(environ: Mapping[str, str]) -> dict[str, str]:
    return {name.upper(): value for name, value in environ.items()}


def _environment_value(
    environ: Mapping[str, str],
    canonical: str,
    legacy: str,
    default: str | None = None,
) -> str | None:
    normalized = _normalized_environment(environ)
    if canonical in normalized:
        return normalized[canonical]
    if legacy in normalized:
        return normalized[legacy]
    return default


def _credential_shaped_variables(environ: Mapping[str, str]) -> list[str]:
    """Return M365/Planner-prefixed names that look like credential material."""
    findings: list[str] = []
    for name in environ:
        upper = name.upper()
        if not upper.startswith((CANONICAL_CONFIG_PREFIX, LEGACY_CONFIG_PREFIX)):
            continue
        if any(marker in upper for marker in _CREDENTIAL_MARKERS):
            findings.append(name)
    return sorted(findings, key=str.upper)


def _alias_conflicts(environ: Mapping[str, str]) -> list[dict[str, str]]:
    """Return names-only conflicts; values are intentionally never returned."""
    normalized = _normalized_environment(environ)
    conflicts: list[dict[str, str]] = []
    for canonical, legacy in _CONFIG_ALIAS_PAIRS:
        if (
            canonical in normalized
            and legacy in normalized
            and normalized[canonical] != normalized[legacy]
        ):
            conflicts.append({"canonical": canonical, "legacy": legacy})
    return conflicts


def _validate_environment(environ: Mapping[str, str]) -> None:
    findings = _credential_shaped_variables(environ)
    if findings:
        raise ConfigurationError(
            "credential-shaped environment variables are forbidden",
            variables=findings,
        )

    conflicts = _alias_conflicts(environ)
    if conflicts:
        raise ConfigurationError(
            "canonical and legacy configuration values conflict",
            conflicts=conflicts,
        )


def _sanitized_validation_issues(exc: ValidationError) -> list[dict[str, str]]:
    """Reduce Pydantic errors to field/type only; raw inputs are discarded."""
    issues: list[dict[str, str]] = []
    for error in exc.errors(include_url=False, include_context=False, include_input=False):
        location = ".".join(str(part) for part in error.get("loc", ())) or "settings"
        issues.append({"field": location, "type": str(error.get("type", "validation_error"))})
    return issues


def configuration_metadata() -> dict[str, object]:
    """Return non-secret compatibility metadata for configuration consumers."""
    return {
        "canonical_namespace": CANONICAL_CONFIG_PREFIX,
        "legacy_namespace": LEGACY_CONFIG_PREFIX,
        "legacy_status": LEGACY_CONFIG_STATUS,
        "legacy_removal_version": LEGACY_CONFIG_REMOVAL_VERSION,
        "dual_definition_policy": "REJECT_DIVERGENT_VALUES",
        "aliases": {canonical: legacy for canonical, legacy in _CONFIG_ALIAS_PAIRS},
    }


class Settings(BaseSettings):
    """Validated non-secret runtime settings for the M365 control plane."""

    model_config = SettingsConfigDict(
        env_prefix="",
        case_sensitive=False,
        extra="ignore",
        populate_by_name=True,
        frozen=True,
        validate_default=True,
    )

    mode: Literal["mock", "live"] = Field(
        default="mock",
        validation_alias=AliasChoices("M365_MODE", "PLANNER_MODE"),
    )
    host: str = Field(
        default="127.0.0.1",
        validation_alias=AliasChoices("M365_MCP_HOST", "PLANNER_MCP_HOST"),
    )
    port: int = Field(
        default=8080,
        ge=1,
        le=65535,
        validation_alias=AliasChoices("M365_MCP_PORT", "PLANNER_MCP_PORT"),
    )
    worker_base_url: str = Field(
        default="http://127.0.0.1:8090",
        validation_alias=AliasChoices("M365_WORKER_URL", "PLANNER_WORKER_URL"),
    )
    state_path: Path = Field(
        default=Path("/var/lib/planner-mcp/state.sqlite3"),
        validation_alias=AliasChoices("M365_STATE_PATH", "PLANNER_STATE_PATH"),
    )
    request_timeout_s: float = Field(
        default=30.0,
        gt=0,
        le=300,
        validation_alias=AliasChoices(
            "M365_REQUEST_TIMEOUT_S",
            "PLANNER_REQUEST_TIMEOUT_S",
        ),
    )
    allow_mutations: bool = Field(
        default=False,
        validation_alias=AliasChoices("M365_ALLOW_MUTATIONS", "PLANNER_ALLOW_MUTATIONS"),
    )
    require_ui_contract_attestation: bool = Field(
        default=True,
        validation_alias=AliasChoices(
            "M365_REQUIRE_UI_ATTESTATION",
            "PLANNER_REQUIRE_UI_ATTESTATION",
        ),
    )
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = Field(
        default="INFO",
        validation_alias=AliasChoices("M365_LOG_LEVEL", "PLANNER_LOG_LEVEL"),
    )
    tool_profile: Literal["full", "planner", "outlook", "read-only"] = Field(
        default="full",
        validation_alias="M365_TOOL_PROFILE",
    )

    def __init__(self, **data: Any) -> None:
        _validate_environment(os.environ)
        super().__init__(**data)

    @field_validator("host")
    @classmethod
    def _host_non_empty(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped or any(char.isspace() for char in stripped):
            raise ValueError("host must be non-empty and contain no whitespace")
        return stripped

    @field_validator("worker_base_url")
    @classmethod
    def _worker_url_http_only(cls, value: str) -> str:
        stripped = value.strip().rstrip("/")
        parsed = urlsplit(stripped)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("worker URL must use http or https and include a host")
        if parsed.username or parsed.password:
            raise ValueError("worker URL must not contain userinfo or credentials")
        return stripped

    @field_validator("state_path")
    @classmethod
    def _state_path_absolute(cls, value: Path) -> Path:
        if not value.is_absolute():
            raise ValueError("state path must be absolute")
        return value

    @model_validator(mode="after")
    def _runtime_invariants(self) -> Settings:
        if self.allow_mutations:
            raise ValueError("public mutations are disabled in product version 0.1.0")
        if self.mode == "live":
            missing = [
                field
                for field in ("worker_base_url", "state_path")
                if field not in self.model_fields_set
            ]
            if missing:
                raise ValueError("live mode requires explicit worker_base_url and state_path")
            if not self.require_ui_contract_attestation:
                raise ValueError("live mode requires UIContract attestation")
        return self

    @property
    def is_mock(self) -> bool:
        return self.mode == "mock"

    @property
    def is_live(self) -> bool:
        return self.mode == "live"

    def public_summary(self) -> dict[str, object]:
        """Return readiness-safe configuration without paths, URLs or secrets."""
        return {
            "mode": self.mode,
            "host": _REDACTED,
            "port": self.port,
            "worker_base_url": _REDACTED,
            "state_path": _REDACTED,
            "request_timeout_s": self.request_timeout_s,
            "allow_mutations": self.allow_mutations,
            "require_ui_contract_attestation": self.require_ui_contract_attestation,
            "log_level": self.log_level,
            "tool_profile": self.tool_profile,
        }

    def __repr__(self) -> str:
        return f"Settings({self.public_summary()!r})"

    def __str__(self) -> str:
        return self.__repr__()


def _missing_live_environment(environ: Mapping[str, str]) -> list[str]:
    normalized = _normalized_environment(environ)
    canonical_mode_present = "M365_MODE" in normalized
    display_index = 0 if canonical_mode_present else 1
    missing: list[str] = []

    for aliases in _LIVE_REQUIRED_PAIRS:
        if not any(normalized.get(name, "").strip() for name in aliases):
            missing.append(aliases[display_index])
    return missing


def load_settings() -> Settings:
    """Load settings from canonical/legacy env and return sanitized typed failures."""
    _validate_environment(os.environ)

    mode = (_environment_value(os.environ, "M365_MODE", "PLANNER_MODE", "mock") or "mock")
    if mode.strip().lower() == "live":
        missing = _missing_live_environment(os.environ)
        if missing:
            raise ConfigurationError(
                "required live configuration is missing",
                missing=missing,
            )

    try:
        return Settings()
    except ConfigurationError:
        raise
    except ValidationError as exc:
        raise ConfigurationError(
            "invalid runtime configuration",
            issues=_sanitized_validation_issues(exc),
        ) from None


def worker_bind_settings(
    environ: Mapping[str, str] | None = None,
) -> tuple[str, int]:
    """Resolve private worker bind settings with the same alias/conflict policy."""
    source = os.environ if environ is None else environ
    _validate_environment(source)

    host = (
        _environment_value(source, "M365_WORKER_HOST", "PLANNER_WORKER_HOST", "127.0.0.1")
        or "127.0.0.1"
    ).strip()
    if not host or any(char.isspace() for char in host):
        raise ConfigurationError(
            "invalid worker bind configuration",
            issues=[{"field": "M365_WORKER_HOST", "type": "invalid_host"}],
        )

    raw_port = _environment_value(source, "M365_WORKER_PORT", "PLANNER_WORKER_PORT", "8090")
    try:
        port = int(raw_port or "8090")
    except ValueError:
        raise ConfigurationError(
            "invalid worker bind configuration",
            issues=[{"field": "M365_WORKER_PORT", "type": "int_parsing"}],
        ) from None

    if not 1 <= port <= 65535:
        raise ConfigurationError(
            "invalid worker bind configuration",
            issues=[{"field": "M365_WORKER_PORT", "type": "range"}],
        )
    return host, port


def browser_runtime_settings(
    environ: Mapping[str, str] | None = None,
) -> tuple[Path, bool, str]:
    """Resolve browser-profile settings without requiring control-plane live settings."""
    source = os.environ if environ is None else environ
    _validate_environment(source)

    profile_raw = _environment_value(
        source,
        "M365_BROWSER_PROFILE_DIR",
        "PLANNER_BROWSER_PROFILE_DIR",
        "/var/lib/planner-worker/profile",
    )
    headless_raw = _environment_value(
        source,
        "M365_BROWSER_HEADLESS",
        "PLANNER_BROWSER_HEADLESS",
        "1",
    )
    mode = _environment_value(source, "M365_MODE", "PLANNER_MODE", "mock") or "mock"

    return Path(profile_raw or "/var/lib/planner-worker/profile"), headless_raw != "0", mode
