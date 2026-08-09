"""Metadata-only synthetic draft attachment semantics for OUT-044."""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import StrEnum

from m365_mcp.apps.outlook.draft_models import SyntheticDraft
from m365_mcp.apps.outlook.readiness import OutlookReadinessReport

_MAX_ATTACHMENTS = 20


class DraftAttachmentAction(StrEnum):
    ADD = "ADD"
    REMOVE = "REMOVE"


@dataclass(frozen=True)
class SyntheticDraftAttachment:
    attachment_key: str
    file_name: str
    size_bytes: int
    artifact_ref: str

    def __post_init__(self) -> None:
        for name in ("attachment_key", "artifact_ref"):
            value = getattr(self, name)
            if not value or value != value.strip() or any(char.isspace() for char in value):
                raise ValueError(f"{name} must be a non-empty semantic token")
        if not self.file_name or self.file_name != self.file_name.strip():
            raise ValueError("file_name must be non-empty and trimmed")
        if self.size_bytes < 0:
            raise ValueError("size_bytes must be non-negative")


@dataclass(frozen=True)
class DraftAttachmentRequest:
    action: DraftAttachmentAction
    draft_key: str
    attachment_key: str

    def __post_init__(self) -> None:
        for name in ("draft_key", "attachment_key"):
            value = getattr(self, name)
            if not value or value != value.strip() or any(char.isspace() for char in value):
                raise ValueError(f"{name} must be a non-empty semantic token")

    def to_payload(self) -> dict[str, object]:
        return {
            "action": self.action.value,
            "draft_key": self.draft_key,
            "attachment_key": self.attachment_key,
        }


@dataclass(frozen=True)
class DraftAttachmentResult:
    action: DraftAttachmentAction
    draft_key: str
    attachment_key: str
    read_back_attachment_keys: tuple[str, ...]
    changed: bool
    verified: bool
    synthetic: bool = True


def apply_draft_attachment_mutation(
    drafts: tuple[SyntheticDraft, ...],
    request: DraftAttachmentRequest,
    *,
    readiness: OutlookReadinessReport,
    catalog: tuple[SyntheticDraftAttachment, ...],
) -> tuple[tuple[SyntheticDraft, ...], DraftAttachmentResult]:
    """Add/remove a controlled attachment reference; never persist file content."""
    if not readiness.ready_for_readonly_discovery:
        raise ValueError("Outlook read-only discovery is not ready")
    current = next((item for item in drafts if item.draft_key == request.draft_key), None)
    if current is None or not current.synthetic:
        raise ValueError("synthetic draft_key not found")

    by_key = {item.attachment_key: item for item in catalog}
    if len(by_key) != len(catalog):
        raise ValueError("attachment catalog keys must be unique")
    if request.action is DraftAttachmentAction.ADD:
        if request.attachment_key not in by_key:
            raise ValueError("attachment_key is not in controlled artifact catalog")
        if request.attachment_key in current.attachment_keys:
            next_keys = current.attachment_keys
        else:
            if len(current.attachment_keys) >= _MAX_ATTACHMENTS:
                raise ValueError("draft attachment list exceeds bounded size")
            next_keys = current.attachment_keys + (request.attachment_key,)
    else:
        next_keys = tuple(
            key for key in current.attachment_keys if key != request.attachment_key
        )

    replacement = replace(current, attachment_keys=next_keys)
    updated = tuple(
        replacement if item.draft_key == request.draft_key else item for item in drafts
    )
    read_back = next(item for item in updated if item.draft_key == request.draft_key)
    if read_back.attachment_keys != next_keys:
        raise RuntimeError("synthetic read-back did not prove draft attachment state")

    return updated, DraftAttachmentResult(
        action=request.action,
        draft_key=request.draft_key,
        attachment_key=request.attachment_key,
        read_back_attachment_keys=read_back.attachment_keys,
        changed=current.attachment_keys != next_keys,
        verified=True,
    )


__all__ = [
    "DraftAttachmentAction",
    "DraftAttachmentRequest",
    "DraftAttachmentResult",
    "SyntheticDraftAttachment",
    "apply_draft_attachment_mutation",
]
