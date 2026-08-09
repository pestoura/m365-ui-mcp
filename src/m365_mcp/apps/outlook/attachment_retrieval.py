"""Controlled synthetic attachment retrieval boundary for OUT-015.

Attachment bytes cross only into an injected artifact sink. Semantic results
contain a CORE-045 opaque artifact reference, never bytes or a raw locator.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Protocol

from m365_mcp.apps.outlook.attachment_metadata import SyntheticAttachment
from m365_mcp.apps.outlook.readiness import OutlookReadinessReport
from m365_mcp.result_references import ArtifactReference, ReferenceKind, make_artifact_reference

_MAX_ATTACHMENT_BYTES = 10 * 1024 * 1024


class AttachmentArtifactSink(Protocol):
    """Narrow sink used to retain validated attachment bytes outside results."""

    def store(self, *, attachment_key: str, media_type: str, payload: bytes) -> str: ...


@dataclass(frozen=True)
class SyntheticAttachmentPayload:
    """Test-only payload bound to one explicit synthetic attachment key."""

    attachment_key: str
    payload: bytes

    def __post_init__(self) -> None:
        if not self.attachment_key or any(char.isspace() for char in self.attachment_key):
            raise ValueError("attachment_key must be a non-empty semantic token")
        if not self.payload:
            raise ValueError("attachment payload must not be empty")
        if len(self.payload) > _MAX_ATTACHMENT_BYTES:
            raise ValueError("attachment payload exceeds retrieval size limit")


@dataclass(frozen=True)
class AttachmentRetrievalResult:
    """Semantic retrieval result containing metadata and an opaque reference only."""

    attachment_key: str
    message_key: str
    file_name: str
    artifact: ArtifactReference
    synthetic: bool

    def to_projection(self) -> dict[str, object]:
        return {
            "attachment_key": self.attachment_key,
            "message_key": self.message_key,
            "file_name": self.file_name,
            "artifact": self.artifact.to_projection(),
            "synthetic": self.synthetic,
        }


def retrieve_synthetic_attachment(
    metadata: SyntheticAttachment,
    payload: SyntheticAttachmentPayload,
    *,
    readiness: OutlookReadinessReport,
    sink: AttachmentArtifactSink,
) -> AttachmentRetrievalResult:
    """Validate, retain and reference one synthetic attachment fail closed."""
    if not readiness.ready_for_readonly_discovery:
        raise ValueError("Outlook read-only discovery is not ready")
    if metadata.attachment_key != payload.attachment_key:
        raise ValueError("attachment payload key does not match metadata")
    if metadata.size_bytes != len(payload.payload):
        raise ValueError("attachment payload size does not match metadata")
    if len(payload.payload) > _MAX_ATTACHMENT_BYTES:
        raise ValueError("attachment payload exceeds retrieval size limit")

    locator = sink.store(
        attachment_key=metadata.attachment_key,
        media_type=metadata.media_type,
        payload=payload.payload,
    )
    if not locator or not locator.strip():
        raise ValueError("artifact sink returned an empty locator")

    content_digest = hashlib.sha256(payload.payload).hexdigest()
    artifact = make_artifact_reference(
        kind=ReferenceKind.ARTIFACT,
        artifact_type="outlook_attachment",
        locator=locator,
        content_digest=content_digest,
        media_type=metadata.media_type,
        size_bytes=len(payload.payload),
    )
    return AttachmentRetrievalResult(
        attachment_key=metadata.attachment_key,
        message_key=metadata.message_key,
        file_name=metadata.file_name,
        artifact=artifact,
        synthetic=True,
    )


__all__ = [
    "AttachmentArtifactSink",
    "AttachmentRetrievalResult",
    "SyntheticAttachmentPayload",
    "retrieve_synthetic_attachment",
]
