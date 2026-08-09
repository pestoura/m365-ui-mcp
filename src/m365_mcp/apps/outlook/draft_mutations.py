"""Synthetic-only Outlook draft lifecycle semantics for OUT-041."""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import StrEnum

from m365_mcp.apps.outlook.draft_models import SyntheticDraft
from m365_mcp.apps.outlook.readiness import OutlookReadinessReport


class DraftMutationAction(StrEnum):
    CREATE = "CREATE"
    UPDATE = "UPDATE"
    DISCARD = "DISCARD"


@dataclass(frozen=True)
class DraftMutationRequest:
    action: DraftMutationAction
    draft_key: str
    subject: str | None = None
    body_text: str | None = None

    def __post_init__(self) -> None:
        if (
            not self.draft_key
            or self.draft_key != self.draft_key.strip()
            or any(char.isspace() for char in self.draft_key)
        ):
            raise ValueError("draft_key must be a non-empty semantic token")
        if self.subject is not None and self.subject != self.subject.strip():
            raise ValueError("subject must be trimmed")
        if self.body_text is not None and "\x00" in self.body_text:
            raise ValueError("body_text must not contain NUL")
        if self.action is DraftMutationAction.CREATE:
            return
        if self.action is DraftMutationAction.UPDATE:
            if self.subject is None and self.body_text is None:
                raise ValueError("update requires subject and/or body_text")
            return
        if self.subject is not None or self.body_text is not None:
            raise ValueError("discard accepts only draft_key")

    def to_payload(self) -> dict[str, object]:
        return {
            "action": self.action.value,
            "draft_key": self.draft_key,
            "subject": self.subject,
            "body_text": self.body_text,
        }


@dataclass(frozen=True)
class DraftMutationResult:
    action: DraftMutationAction
    draft_key: str
    previous_exists: bool
    read_back_exists: bool
    changed: bool
    verified: bool
    synthetic: bool = True


def get_synthetic_draft(
    drafts: tuple[SyntheticDraft, ...],
    draft_key: str,
) -> SyntheticDraft:
    """Read one synthetic draft by semantic key."""
    draft = next((item for item in drafts if item.draft_key == draft_key), None)
    if draft is None:
        raise ValueError("synthetic draft_key not found")
    return draft


def apply_draft_mutation(
    drafts: tuple[SyntheticDraft, ...],
    request: DraftMutationRequest,
    *,
    readiness: OutlookReadinessReport,
) -> tuple[tuple[SyntheticDraft, ...], DraftMutationResult]:
    """Create, update or discard one synthetic draft with immediate read-back."""
    if not readiness.ready_for_readonly_discovery:
        raise ValueError("Outlook read-only discovery is not ready")
    if any(not draft.synthetic for draft in drafts):
        raise ValueError("OUT-041 requires synthetic draft state")

    current = next((item for item in drafts if item.draft_key == request.draft_key), None)
    if request.action is DraftMutationAction.CREATE:
        if current is not None:
            raise ValueError("draft_key already exists")
        created = SyntheticDraft(
            draft_key=request.draft_key,
            subject=request.subject or "",
            body_text=request.body_text or "",
        )
        updated = drafts + (created,)
        read_back_exists = any(item.draft_key == request.draft_key for item in updated)
        if not read_back_exists:
            raise RuntimeError("synthetic read-back did not prove draft creation")
        return updated, DraftMutationResult(
            action=request.action,
            draft_key=request.draft_key,
            previous_exists=False,
            read_back_exists=True,
            changed=True,
            verified=True,
        )

    if request.action is DraftMutationAction.UPDATE:
        if current is None:
            raise ValueError("synthetic draft_key not found")
        replacement = replace(
            current,
            subject=current.subject if request.subject is None else request.subject,
            body_text=current.body_text if request.body_text is None else request.body_text,
        )
        updated = tuple(
            replacement if item.draft_key == request.draft_key else item for item in drafts
        )
        read_back = get_synthetic_draft(updated, request.draft_key)
        if read_back != replacement:
            raise RuntimeError("synthetic read-back did not prove draft update")
        return updated, DraftMutationResult(
            action=request.action,
            draft_key=request.draft_key,
            previous_exists=True,
            read_back_exists=True,
            changed=replacement != current,
            verified=True,
        )

    updated = tuple(item for item in drafts if item.draft_key != request.draft_key)
    read_back_exists = any(item.draft_key == request.draft_key for item in updated)
    if read_back_exists:
        raise RuntimeError("synthetic read-back did not prove draft discard")
    return updated, DraftMutationResult(
        action=request.action,
        draft_key=request.draft_key,
        previous_exists=current is not None,
        read_back_exists=False,
        changed=current is not None,
        verified=True,
    )


__all__ = [
    "DraftMutationAction",
    "DraftMutationRequest",
    "DraftMutationResult",
    "apply_draft_mutation",
    "get_synthetic_draft",
]
