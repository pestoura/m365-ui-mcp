"""Tenant-neutral synthetic template/snippet integration for OUT-047."""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import StrEnum

from m365_mcp.apps.outlook.draft_models import SyntheticDraft
from m365_mcp.apps.outlook.readiness import OutlookReadinessReport


class DraftInsertMode(StrEnum):
    REPLACE_BODY = "REPLACE_BODY"
    APPEND_BODY = "APPEND_BODY"


@dataclass(frozen=True)
class SyntheticDraftInsert:
    insert_key: str
    body_text: str
    subject: str | None = None

    def __post_init__(self) -> None:
        if (
            not self.insert_key
            or self.insert_key != self.insert_key.strip()
            or any(char.isspace() for char in self.insert_key)
        ):
            raise ValueError("insert_key must be a non-empty semantic token")
        if "\x00" in self.body_text:
            raise ValueError("body_text must not contain NUL")
        if self.subject is not None and self.subject != self.subject.strip():
            raise ValueError("subject must be trimmed")


@dataclass(frozen=True)
class DraftInsertRequest:
    draft_key: str
    insert_key: str
    mode: DraftInsertMode

    def __post_init__(self) -> None:
        for name in ("draft_key", "insert_key"):
            value = getattr(self, name)
            if not value or value != value.strip() or any(char.isspace() for char in value):
                raise ValueError(f"{name} must be a non-empty semantic token")

    def to_payload(self) -> dict[str, object]:
        return {
            "draft_key": self.draft_key,
            "insert_key": self.insert_key,
            "mode": self.mode.value,
        }


@dataclass(frozen=True)
class DraftInsertResult:
    draft_key: str
    insert_key: str
    mode: DraftInsertMode
    changed: bool
    verified: bool
    synthetic: bool = True


def apply_draft_insert(
    drafts: tuple[SyntheticDraft, ...],
    request: DraftInsertRequest,
    *,
    readiness: OutlookReadinessReport,
    catalog: tuple[SyntheticDraftInsert, ...],
) -> tuple[tuple[SyntheticDraft, ...], DraftInsertResult]:
    """Apply one known tenant-neutral insert and prove the resulting draft state."""
    if not readiness.ready_for_readonly_discovery:
        raise ValueError("Outlook read-only discovery is not ready")
    current = next((item for item in drafts if item.draft_key == request.draft_key), None)
    if current is None or not current.synthetic:
        raise ValueError("synthetic draft_key not found")

    matches = tuple(item for item in catalog if item.insert_key == request.insert_key)
    if len(matches) != 1:
        raise ValueError("insert_key must resolve to exactly one known insert")
    insert = matches[0]

    if request.mode is DraftInsertMode.REPLACE_BODY:
        body_text = insert.body_text
    else:
        separator = "\n" if current.body_text and insert.body_text else ""
        body_text = f"{current.body_text}{separator}{insert.body_text}"
    subject = current.subject if insert.subject is None else insert.subject

    replacement = replace(current, subject=subject, body_text=body_text)
    updated = tuple(
        replacement if item.draft_key == request.draft_key else item for item in drafts
    )
    read_back = next(item for item in updated if item.draft_key == request.draft_key)
    if read_back.subject != subject or read_back.body_text != body_text:
        raise RuntimeError("synthetic read-back did not prove template/snippet state")

    return updated, DraftInsertResult(
        draft_key=request.draft_key,
        insert_key=request.insert_key,
        mode=request.mode,
        changed=replacement != current,
        verified=True,
    )


__all__ = [
    "DraftInsertMode",
    "DraftInsertRequest",
    "DraftInsertResult",
    "SyntheticDraftInsert",
    "apply_draft_insert",
]
