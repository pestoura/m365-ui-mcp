"""Bounded artifact/evidence references for CORE-045.

References let semantic results point at separately retained artifacts without
embedding large payloads or storage locations. Raw locators are hashed at
construction time and never projected by this model.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from enum import StrEnum


class ReferenceKind(StrEnum):
    """Closed semantic reference roles."""

    ARTIFACT = "ARTIFACT"
    EVIDENCE = "EVIDENCE"


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _validate_digest(value: str, *, field_name: str) -> None:
    if len(value) != 64 or any(char not in "0123456789abcdef" for char in value):
        raise ValueError(f"{field_name} must be lowercase SHA-256 hex")


def _semantic_token(value: str, *, field_name: str) -> str:
    normalized = value.strip()
    if not normalized or any(char.isspace() for char in normalized):
        raise ValueError(f"{field_name} must be a non-empty semantic token")
    return normalized


@dataclass(frozen=True)
class ArtifactReference:
    """Content-addressed result reference without exposing its storage locator."""

    kind: ReferenceKind
    artifact_type: str
    locator_digest: str
    content_digest: str
    media_type: str
    size_bytes: int | None = None

    def __post_init__(self) -> None:
        _semantic_token(self.artifact_type, field_name="artifact_type")
        _validate_digest(self.locator_digest, field_name="locator_digest")
        _validate_digest(self.content_digest, field_name="content_digest")
        normalized_media_type = self.media_type.strip()
        if not normalized_media_type or "/" not in normalized_media_type:
            raise ValueError("media_type must be a bounded MIME type")
        if self.size_bytes is not None and self.size_bytes < 0:
            raise ValueError("size_bytes must be non-negative")

    @property
    def reference_id(self) -> str:
        """Return a stable opaque identity for dedupe/linking."""
        return _sha256(
            "|".join(
                (
                    self.kind.value,
                    self.artifact_type,
                    self.locator_digest,
                    self.content_digest,
                    self.media_type,
                    str(self.size_bytes) if self.size_bytes is not None else "",
                )
            )
        )

    def to_projection(self) -> dict[str, object]:
        """Project only bounded metadata; storage locator remains hidden."""
        projected: dict[str, object] = {
            "reference_id": self.reference_id,
            "kind": self.kind.value,
            "artifact_type": self.artifact_type,
            "content_digest": self.content_digest,
            "media_type": self.media_type,
        }
        if self.size_bytes is not None:
            projected["size_bytes"] = self.size_bytes
        return projected


def make_artifact_reference(
    *,
    kind: ReferenceKind,
    artifact_type: str,
    locator: str,
    content_digest: str,
    media_type: str,
    size_bytes: int | None = None,
) -> ArtifactReference:
    """Create a reference while immediately discarding the raw locator."""
    normalized_locator = locator.strip()
    if not normalized_locator:
        raise ValueError("artifact locator must not be empty")
    return ArtifactReference(
        kind=kind,
        artifact_type=artifact_type,
        locator_digest=_sha256(normalized_locator),
        content_digest=content_digest,
        media_type=media_type,
        size_bytes=size_bytes,
    )


@dataclass(frozen=True)
class ReferencedResult:
    """Attach deduplicated references to an already-produced semantic result."""

    result: object
    references: tuple[ArtifactReference, ...]

    def __post_init__(self) -> None:
        ids = tuple(reference.reference_id for reference in self.references)
        if len(set(ids)) != len(ids):
            raise ValueError("result references must be unique")

    def reference_projection(self) -> tuple[dict[str, object], ...]:
        return tuple(reference.to_projection() for reference in self.references)


__all__ = [
    "ArtifactReference",
    "ReferenceKind",
    "ReferencedResult",
    "make_artifact_reference",
]
