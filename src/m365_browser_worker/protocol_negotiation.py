"""Fail-closed control-plane/worker protocol negotiation.

Compatibility is runtime state established only by an explicit handshake. A
matching package version or shared constant does not by itself make readiness
true.
"""

from __future__ import annotations

from dataclasses import dataclass

from pydantic import BaseModel, ConfigDict, Field, field_validator

from m365_browser_worker.protocol import PROTOCOL_SCHEMA_VERSION

SUPPORTED_PROTOCOL_VERSIONS = (PROTOCOL_SCHEMA_VERSION,)


class ProtocolNegotiationRequest(BaseModel):
    """Bounded peer version advertisement from the private control plane."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    supported_versions: list[str] = Field(min_length=1, max_length=8)

    @field_validator("supported_versions")
    @classmethod
    def validate_versions(cls, versions: list[str]) -> list[str]:
        normalized: list[str] = []
        for version in versions:
            if not version or len(version) > 32 or not version.replace(".", "").isdigit():
                raise ValueError("protocol versions must be bounded numeric dotted strings")
            if version not in normalized:
                normalized.append(version)
        return normalized


class ProtocolNegotiationResponse(BaseModel):
    """Sanitized handshake result."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    compatible: bool
    negotiated_version: str | None
    worker_supported_versions: tuple[str, ...]


@dataclass
class ProtocolNegotiator:
    """Process-local compatibility state for one worker instance."""

    supported_versions: tuple[str, ...] = SUPPORTED_PROTOCOL_VERSIONS
    _negotiated_version: str | None = None

    @property
    def compatible(self) -> bool:
        return self._negotiated_version is not None

    @property
    def negotiated_version(self) -> str | None:
        return self._negotiated_version

    def reset(self) -> None:
        """Fail closed after peer/session lifecycle reset."""
        self._negotiated_version = None

    def negotiate(self, peer_supported_versions: list[str]) -> ProtocolNegotiationResponse:
        """Select the newest mutually supported numeric dotted version."""
        mutual = set(self.supported_versions).intersection(peer_supported_versions)
        if not mutual:
            self.reset()
            return ProtocolNegotiationResponse(
                compatible=False,
                negotiated_version=None,
                worker_supported_versions=self.supported_versions,
            )

        def version_key(value: str) -> tuple[int, ...]:
            return tuple(int(part) for part in value.split("."))

        selected = max(mutual, key=version_key)
        self._negotiated_version = selected
        return ProtocolNegotiationResponse(
            compatible=True,
            negotiated_version=selected,
            worker_supported_versions=self.supported_versions,
        )

    def snapshot(self) -> dict[str, object]:
        """Return only protocol metadata; no peer/session content."""
        return {
            "compatible": self.compatible,
            "negotiated_version": self.negotiated_version,
            "supported_versions": list(self.supported_versions),
        }


__all__ = [
    "SUPPORTED_PROTOCOL_VERSIONS",
    "ProtocolNegotiationRequest",
    "ProtocolNegotiationResponse",
    "ProtocolNegotiator",
]
