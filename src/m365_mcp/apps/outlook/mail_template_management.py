"""Tenant-neutral synthetic full mail template management for OUT-074."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from m365_mcp.apps.outlook.draft_template_mutations import SyntheticDraftInsert
from m365_mcp.apps.outlook.readiness import OutlookReadinessReport


def _validate_token(name: str, value: str) -> None:
    if not value or value != value.strip() or any(char.isspace() for char in value):
        raise ValueError(f"{name} must be a non-empty semantic token")


class MailTemplateAction(StrEnum):
    CREATE = "CREATE"
    UPDATE = "UPDATE"
    DELETE = "DELETE"


@dataclass(frozen=True)
class SyntheticMailTemplate:
    template_key: str
    subject: str
    body_text: str

    def __post_init__(self) -> None:
        _validate_token("template_key", self.template_key)
        if self.subject != self.subject.strip():
            raise ValueError("subject must be trimmed")
        if "\x00" in self.subject or "\x00" in self.body_text:
            raise ValueError("template text must not contain NUL")

    def to_projection(self) -> dict[str, object]:
        return {
            "template_key": self.template_key,
            "subject": self.subject,
            "body_text": self.body_text,
            "synthetic": True,
        }

    def to_draft_insert(self) -> SyntheticDraftInsert:
        return SyntheticDraftInsert(
            insert_key=self.template_key,
            subject=self.subject,
            body_text=self.body_text,
        )


@dataclass(frozen=True)
class MailTemplateRequest:
    action: MailTemplateAction
    template_key: str
    template: SyntheticMailTemplate | None = None

    def __post_init__(self) -> None:
        _validate_token("template_key", self.template_key)
        if self.action in {MailTemplateAction.CREATE, MailTemplateAction.UPDATE}:
            if self.template is None or self.template.template_key != self.template_key:
                raise ValueError("CREATE/UPDATE requires a matching synthetic template")
        elif self.template is not None:
            raise ValueError("DELETE does not accept template")

    def to_payload(self) -> dict[str, object]:
        return {
            "action": self.action.value,
            "template_key": self.template_key,
            "template": None if self.template is None else self.template.to_projection(),
        }


@dataclass(frozen=True)
class MailTemplateResult:
    action: MailTemplateAction
    template_key: str
    changed: bool
    read_back: SyntheticMailTemplate | None
    verified: bool
    synthetic: bool = True


def _find(
    catalog: tuple[SyntheticMailTemplate, ...],
    template_key: str,
) -> SyntheticMailTemplate | None:
    matches = tuple(item for item in catalog if item.template_key == template_key)
    if len(matches) > 1:
        raise RuntimeError("synthetic mail template catalog became ambiguous")
    return matches[0] if matches else None


def mutate_mail_template_catalog(
    catalog: tuple[SyntheticMailTemplate, ...],
    request: MailTemplateRequest,
    *,
    readiness: OutlookReadinessReport,
) -> tuple[tuple[SyntheticMailTemplate, ...], MailTemplateResult]:
    """Apply one synthetic full-template mutation with exact read-back."""
    if not readiness.ready_for_readonly_discovery:
        raise ValueError("Outlook read-only discovery is not ready")

    current = _find(catalog, request.template_key)
    if request.action is MailTemplateAction.CREATE:
        if current is not None:
            raise ValueError("CREATE requires a new template_key")
        assert request.template is not None
        updated = catalog + (request.template,)
        changed = True
    elif request.action is MailTemplateAction.UPDATE:
        if current is None:
            raise ValueError("UPDATE requires an existing template_key")
        assert request.template is not None
        updated = tuple(
            request.template if item.template_key == request.template_key else item
            for item in catalog
        )
        changed = current != request.template
    else:
        updated = tuple(item for item in catalog if item.template_key != request.template_key)
        changed = current is not None

    updated = tuple(sorted(updated, key=lambda item: item.template_key))
    read_back = _find(updated, request.template_key)
    expected = None if request.action is MailTemplateAction.DELETE else request.template
    if read_back != expected:
        raise RuntimeError("synthetic read-back did not prove mail template catalog state")

    return updated, MailTemplateResult(
        action=request.action,
        template_key=request.template_key,
        changed=changed,
        read_back=read_back,
        verified=True,
    )


__all__ = [
    "MailTemplateAction",
    "MailTemplateRequest",
    "MailTemplateResult",
    "SyntheticMailTemplate",
    "mutate_mail_template_catalog",
]
