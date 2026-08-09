"""Tenant-neutral synthetic My Templates/snippet management for OUT-075."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from m365_mcp.apps.outlook.draft_template_mutations import SyntheticDraftInsert
from m365_mcp.apps.outlook.readiness import OutlookReadinessReport


def _validate_token(name: str, value: str) -> None:
    if not value or value != value.strip() or any(char.isspace() for char in value):
        raise ValueError(f"{name} must be a non-empty semantic token")


class SnippetAction(StrEnum):
    CREATE = "CREATE"
    UPDATE = "UPDATE"
    DELETE = "DELETE"


@dataclass(frozen=True)
class SyntheticSnippet:
    snippet_key: str
    body_text: str

    def __post_init__(self) -> None:
        _validate_token("snippet_key", self.snippet_key)
        if "\x00" in self.body_text:
            raise ValueError("body_text must not contain NUL")

    def to_projection(self) -> dict[str, object]:
        return {
            "snippet_key": self.snippet_key,
            "body_text": self.body_text,
            "synthetic": True,
        }

    def to_draft_insert(self) -> SyntheticDraftInsert:
        return SyntheticDraftInsert(
            insert_key=self.snippet_key,
            body_text=self.body_text,
            subject=None,
        )


@dataclass(frozen=True)
class SnippetRequest:
    action: SnippetAction
    snippet_key: str
    snippet: SyntheticSnippet | None = None

    def __post_init__(self) -> None:
        _validate_token("snippet_key", self.snippet_key)
        if self.action in {SnippetAction.CREATE, SnippetAction.UPDATE}:
            if self.snippet is None or self.snippet.snippet_key != self.snippet_key:
                raise ValueError("CREATE/UPDATE requires a matching synthetic snippet")
        elif self.snippet is not None:
            raise ValueError("DELETE does not accept snippet")

    def to_payload(self) -> dict[str, object]:
        return {
            "action": self.action.value,
            "snippet_key": self.snippet_key,
            "snippet": None if self.snippet is None else self.snippet.to_projection(),
        }


@dataclass(frozen=True)
class SnippetResult:
    action: SnippetAction
    snippet_key: str
    changed: bool
    read_back: SyntheticSnippet | None
    verified: bool
    synthetic: bool = True


def _find(
    catalog: tuple[SyntheticSnippet, ...],
    snippet_key: str,
) -> SyntheticSnippet | None:
    matches = tuple(item for item in catalog if item.snippet_key == snippet_key)
    if len(matches) > 1:
        raise RuntimeError("synthetic snippet catalog became ambiguous")
    return matches[0] if matches else None


def mutate_snippet_catalog(
    catalog: tuple[SyntheticSnippet, ...],
    request: SnippetRequest,
    *,
    readiness: OutlookReadinessReport,
) -> tuple[tuple[SyntheticSnippet, ...], SnippetResult]:
    """Apply one synthetic snippet mutation with exact read-back."""
    if not readiness.ready_for_readonly_discovery:
        raise ValueError("Outlook read-only discovery is not ready")

    current = _find(catalog, request.snippet_key)
    if request.action is SnippetAction.CREATE:
        if current is not None:
            raise ValueError("CREATE requires a new snippet_key")
        assert request.snippet is not None
        updated = catalog + (request.snippet,)
        changed = True
    elif request.action is SnippetAction.UPDATE:
        if current is None:
            raise ValueError("UPDATE requires an existing snippet_key")
        assert request.snippet is not None
        updated = tuple(
            request.snippet if item.snippet_key == request.snippet_key else item
            for item in catalog
        )
        changed = current != request.snippet
    else:
        updated = tuple(item for item in catalog if item.snippet_key != request.snippet_key)
        changed = current is not None

    updated = tuple(sorted(updated, key=lambda item: item.snippet_key))
    read_back = _find(updated, request.snippet_key)
    expected = None if request.action is SnippetAction.DELETE else request.snippet
    if read_back != expected:
        raise RuntimeError("synthetic read-back did not prove snippet catalog state")

    return updated, SnippetResult(
        action=request.action,
        snippet_key=request.snippet_key,
        changed=changed,
        read_back=read_back,
        verified=True,
    )


__all__ = [
    "SnippetAction",
    "SnippetRequest",
    "SnippetResult",
    "SyntheticSnippet",
    "mutate_snippet_catalog",
]
