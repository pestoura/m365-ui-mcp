"""Tenant-neutral synthetic recipient resolution for OUT-042."""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import StrEnum

from m365_mcp.apps.outlook.draft_models import SyntheticDraft
from m365_mcp.apps.outlook.readiness import OutlookReadinessReport

_MAX_RECIPIENTS_PER_FIELD = 20


class RecipientField(StrEnum):
    TO = "TO"
    CC = "CC"
    BCC = "BCC"


@dataclass(frozen=True)
class SyntheticRecipientCandidate:
    recipient_key: str
    aliases: tuple[str, ...]

    def __post_init__(self) -> None:
        values = (self.recipient_key, *self.aliases)
        for value in values:
            if not value or value != value.strip():
                raise ValueError("recipient keys and aliases must be non-empty and trimmed")
        if len(self.aliases) != len(set(alias.lower() for alias in self.aliases)):
            raise ValueError("recipient aliases must be unique")


@dataclass(frozen=True)
class RecipientAssignmentRequest:
    draft_key: str
    field: RecipientField
    queries: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.draft_key or self.draft_key != self.draft_key.strip():
            raise ValueError("draft_key must be non-empty and trimmed")
        if len(self.queries) > _MAX_RECIPIENTS_PER_FIELD:
            raise ValueError("recipient field exceeds bounded size")
        for query in self.queries:
            if not query or query != query.strip():
                raise ValueError("recipient query must be non-empty and trimmed")

    def to_payload(self) -> dict[str, object]:
        return {
            "draft_key": self.draft_key,
            "field": self.field.value,
            "queries": self.queries,
        }


@dataclass(frozen=True)
class RecipientAssignmentResult:
    draft_key: str
    field: RecipientField
    resolved_keys: tuple[str, ...]
    changed: bool
    verified: bool
    synthetic: bool = True


def resolve_recipient(
    query: str,
    candidates: tuple[SyntheticRecipientCandidate, ...],
) -> SyntheticRecipientCandidate:
    """Resolve exactly one tenant-neutral candidate; ambiguity fails closed."""
    normalized = query.strip().lower()
    matches = tuple(
        candidate
        for candidate in candidates
        if normalized
        in {
            candidate.recipient_key.lower(),
            *(alias.lower() for alias in candidate.aliases),
        }
    )
    if not matches:
        raise ValueError("recipient query did not resolve")
    if len(matches) != 1:
        raise ValueError("recipient query is ambiguous")
    return matches[0]


def apply_recipient_assignment(
    drafts: tuple[SyntheticDraft, ...],
    request: RecipientAssignmentRequest,
    *,
    readiness: OutlookReadinessReport,
    candidates: tuple[SyntheticRecipientCandidate, ...],
) -> tuple[tuple[SyntheticDraft, ...], RecipientAssignmentResult]:
    """Resolve and replace one recipient field with immediate read-back."""
    if not readiness.ready_for_readonly_discovery:
        raise ValueError("Outlook read-only discovery is not ready")
    current = next((item for item in drafts if item.draft_key == request.draft_key), None)
    if current is None or not current.synthetic:
        raise ValueError("synthetic draft_key not found")

    resolved = tuple(resolve_recipient(query, candidates).recipient_key for query in request.queries)
    if len(resolved) != len(set(resolved)):
        raise ValueError("recipient queries resolve to duplicate identities")

    field_name = {
        RecipientField.TO: "to_keys",
        RecipientField.CC: "cc_keys",
        RecipientField.BCC: "bcc_keys",
    }[request.field]
    previous = getattr(current, field_name)
    replacement = replace(current, **{field_name: resolved})
    updated = tuple(
        replacement if item.draft_key == request.draft_key else item for item in drafts
    )
    read_back = next(item for item in updated if item.draft_key == request.draft_key)
    if getattr(read_back, field_name) != resolved:
        raise RuntimeError("synthetic read-back did not prove recipient assignment")

    return updated, RecipientAssignmentResult(
        draft_key=request.draft_key,
        field=request.field,
        resolved_keys=resolved,
        changed=previous != resolved,
        verified=True,
    )


__all__ = [
    "RecipientAssignmentRequest",
    "RecipientAssignmentResult",
    "RecipientField",
    "SyntheticRecipientCandidate",
    "apply_recipient_assignment",
    "resolve_recipient",
]
