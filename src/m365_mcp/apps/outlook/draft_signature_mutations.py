"""Tenant-neutral synthetic draft signature integration for OUT-046."""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import StrEnum

from m365_mcp.apps.outlook.draft_models import SyntheticDraft
from m365_mcp.apps.outlook.readiness import OutlookReadinessReport


class DraftSignatureAction(StrEnum):
    APPLY = "APPLY"
    CLEAR = "CLEAR"


@dataclass(frozen=True)
class SyntheticSignature:
    signature_key: str
    enabled: bool = True

    def __post_init__(self) -> None:
        if (
            not self.signature_key
            or self.signature_key != self.signature_key.strip()
            or any(char.isspace() for char in self.signature_key)
        ):
            raise ValueError("signature_key must be a non-empty semantic token")


@dataclass(frozen=True)
class DraftSignatureRequest:
    action: DraftSignatureAction
    draft_key: str
    signature_key: str | None = None

    def __post_init__(self) -> None:
        if (
            not self.draft_key
            or self.draft_key != self.draft_key.strip()
            or any(char.isspace() for char in self.draft_key)
        ):
            raise ValueError("draft_key must be a non-empty semantic token")
        if self.action is DraftSignatureAction.APPLY:
            if self.signature_key is None:
                raise ValueError("apply requires signature_key")
            if (
                not self.signature_key
                or self.signature_key != self.signature_key.strip()
                or any(char.isspace() for char in self.signature_key)
            ):
                raise ValueError("signature_key must be a non-empty semantic token")
        elif self.signature_key is not None:
            raise ValueError("clear must not include signature_key")

    def to_payload(self) -> dict[str, object]:
        return {
            "action": self.action.value,
            "draft_key": self.draft_key,
            "signature_key": self.signature_key,
        }


@dataclass(frozen=True)
class DraftSignatureResult:
    action: DraftSignatureAction
    draft_key: str
    previous_signature_key: str | None
    read_back_signature_key: str | None
    changed: bool
    verified: bool
    synthetic: bool = True


def apply_draft_signature(
    drafts: tuple[SyntheticDraft, ...],
    request: DraftSignatureRequest,
    *,
    readiness: OutlookReadinessReport,
    signatures: tuple[SyntheticSignature, ...],
) -> tuple[tuple[SyntheticDraft, ...], DraftSignatureResult]:
    """Apply/clear a known synthetic signature key with immediate read-back."""
    if not readiness.ready_for_readonly_discovery:
        raise ValueError("Outlook read-only discovery is not ready")
    current = next((item for item in drafts if item.draft_key == request.draft_key), None)
    if current is None or not current.synthetic:
        raise ValueError("synthetic draft_key not found")

    if request.action is DraftSignatureAction.APPLY:
        matches = tuple(
            item for item in signatures if item.signature_key == request.signature_key
        )
        if len(matches) != 1:
            raise ValueError("signature_key must resolve to exactly one known signature")
        if not matches[0].enabled:
            raise ValueError("signature is not enabled")
        next_key = matches[0].signature_key
    else:
        next_key = None

    replacement = replace(current, signature_key=next_key)
    updated = tuple(
        replacement if item.draft_key == request.draft_key else item for item in drafts
    )
    read_back = next(item for item in updated if item.draft_key == request.draft_key)
    if read_back.signature_key != next_key:
        raise RuntimeError("synthetic read-back did not prove draft signature state")

    return updated, DraftSignatureResult(
        action=request.action,
        draft_key=request.draft_key,
        previous_signature_key=current.signature_key,
        read_back_signature_key=read_back.signature_key,
        changed=current.signature_key != next_key,
        verified=True,
    )


__all__ = [
    "DraftSignatureAction",
    "DraftSignatureRequest",
    "DraftSignatureResult",
    "SyntheticSignature",
    "apply_draft_signature",
]
