"""Typed, fail-closed runtime configuration with a non-secret environment boundary."""

from __future__ import annotations

import os
from collections.abc import Mapping
from pathlib import Path
from typing import Any, Literal
from urllib.parse import urlsplit

from pydantic import Field, ValidationError, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from .errors import ConfigurationError

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
_LIVE_REQUIRED_ENV = ("PLANNER_WORKER_URL", "PLANNER_STATE_PATH")
_REDACTED = "[REDACTED]"


def _credential_shaped_variables(environ: Mapping[str, str]) -> list[str]:
    """Return Planner-prefixed environment names that look like credential material."""
    findings: list[str] = []
    for name in environ:
        upper = name.upper()
        if not upper.startswith("PLANNER_"):
            continue
        if any(marker in upper for marker in _CREDENTIAL_MARKERS):
            findings.append(name)
    return sorted(findings)


def _reject_credential_environment(environ: Mapping[str, str]) -> None:
    findings = _credential_shaped_variables(environ)
    if findings:
        raise ConfigurationError(
            "credential-shaped environment variables are forbidden",
            variables=findings,
        )


def _sanitized_validation_issues(exc: ValidationError) -> list[dict[str, str]]:
    """Reduce Pydantic errors to field/type only; raw inputs are deliberately discarded."""
    issues: list[dict[str, str]] = []
    for error in exc.errors(include_url=False, include_context=False, include_input=False):
        location = ".".join(str(part) for part in error.get("loc", ())) or "settings"
        issues.append({"field": location, "type": str(error.get("type", "validation_error"))})
    return issues


class Settings(BaseSettings):
    """Validated non-secret runtime settings for the control plane."""

    model_config = SettingsConfigDict(
        env_prefix="PLANNER_",
        case_sensitive=False,
        extra="ignore",
        populate_by_name=True,
        frozen=True,
        validate_default=True,
    )

    mode: Literal["mock", "live"] = "mock"
    host: str = Field(default="127.0.0.1", validation_alias="PLANNER_MCP_HOST")
    port: int = Field(default=8080, ge=1, le=65535, validation_alias="PLANNER_MCP_PORT")
    worker_base_url: str = Field(
        default="http://127.0.0.1:8090",
        validation_alias="PLANNER_WORKER_URL",
    )
    state_path: Path = Field(
        default=Path("/var/lib/planner-mcp/state.sqlite3"),
        validation_alias="PLANNER_STATE_PATH",
    )
    request_timeout_s: float = Field(
        default=30.0,
        gt=0,
        le=300,
        validation_alias="PLANNER_REQUEST_TIMEOUT_S",
    )
    allow_mutations: bool = Field(default=False, validation_alias="PLANNER_ALLOW_MUTATIONS")
    require_ui_contract_attestation: bool = Field(
        default=True,
        validation_alias="PLANNER_REQUIRE_UI_ATTESTATION",
    )
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = Field(
        default="INFO",
        validation_alias="PLANNER_LOG_LEVEL",
    )

    def __init__(self, **data: Any) -> None:
        _reject_credential_environment(os.environ)
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
        """Return readiness-safe configuration without paths, URLs or credential material."""
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
        }

    def __repr__(self) -> str:
        return f"Settings({self.public_summary()!r})"

    def __str__(self) -> str:
        return self.__repr__()


def load_settings() -> Settings:
    """Load settings from the environment and convert failures to a sanitized typed error."""
    _reject_credential_environment(os.environ)

    mode = os.getenv("PLANNER_MODE", "mock").strip().lower()
    if mode == "live":
        missing = [name for name in _LIVE_REQUIRED_ENV if not os.getenv(name, "").strip()]
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
