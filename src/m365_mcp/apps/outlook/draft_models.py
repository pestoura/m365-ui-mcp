"""Tenant-neutral synthetic draft state shared by Outlook Wave D/E lanes."""

from __future__ import annotations

from dataclasses import dataclass


def _semantic_token(value: str, name: str) -> str:
    if not value or value != value.strip() or any(char.isspace() for char in value):
        raise ValueError(f"{name} must be a non-empty semantic token")
    return value


@dataclass(frozen=True)
class SyntheticDraft:
    """Synthetic draft state containing only tenant-neutral semantic keys/content."""

    draft_key: str
    subject: str = ""
    body_text: str = ""
    from_identity_key: str = "primary"
    to_keys: tuple[str, ...] = ()
    cc_keys: tuple[str, ...] = ()
    bcc_keys: tuple[str, ...] = ()
    attachment_keys: tuple[str, ...] = ()
    importance: str = "NORMAL"
    sensitivity: str = "NORMAL"
    signature_key: str | None = None
    read_receipt_requested: bool = False
    delivery_receipt_requested: bool = False
    synthetic: bool = True

    def __post_init__(self) -> None:
        _semantic_token(self.draft_key, "draft_key")
        _semantic_token(self.from_identity_key, "from_identity_key")
        for name in ("to_keys", "cc_keys", "bcc_keys", "attachment_keys"):
            values = getattr(self, name)
            if len(values) != len(set(values)):
                raise ValueError(f"{name} must not contain duplicates")
            for value in values:
                _semantic_token(value, name)
        if self.signature_key is not None:
            _semantic_token(self.signature_key, "signature_key")
        if self.subject != self.subject.strip():
            raise ValueError("subject must be trimmed")
        if "\x00" in self.body_text:
            raise ValueError("body_text must not contain NUL")


def default_synthetic_drafts() -> tuple[SyntheticDraft, ...]:
    """Return a deterministic tenant-neutral draft fixture."""
    return (
        SyntheticDraft(
            draft_key="draft-001",
            subject="Synthetic project update",
            body_text="Synthetic draft body.",
        ),
    )


__all__ = ["SyntheticDraft", "default_synthetic_drafts"]
