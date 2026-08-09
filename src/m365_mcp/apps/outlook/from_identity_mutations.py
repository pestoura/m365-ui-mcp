"""Tenant-neutral synthetic From identity selection for OUT-043."""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import StrEnum

from m365_mcp.apps.outlook.draft_models import SyntheticDraft
from m365_mcp.apps.outlook.readiness import OutlookReadinessReport


class FromIdentityMode(StrEnum):
    PRIMARY = "PRIMARY"
    SHARED = "SHARED"
    DELEGATED = "DELEGATED"


@dataclass(frozen=True)
class SyntheticFromIdentity:
    identity_key: str
    mode: FromIdentityMode
    authorized: bool

    def __post_init__(self) -> None:
        if (
            not self.identity_key
            or self.identity_key != self.identity_key.strip()
            or any(char.isspace() for char in self.identity_key)
        ):
            raise ValueError("identity_key must be a non-empty semantic token")


@dataclass(frozen=True)
class FromIdentityRequest:
    draft_key: str
    identity_key: str

    def __post_init__(self) -> None:
        for name in ("draft_key", "identity_key"):
            value = getattr(self, name)
            if not value or value != value.strip() or any(char.isspace() for char in value):
                raise ValueError(f"{name} must be a non-empty semantic token")

    def to_payload(self) -> dict[str, object]:
        return {"draft_key": self.draft_key, "identity_key": self.identity_key}


@dataclass(frozen=True)
class FromIdentityResult:
    draft_key: str
    previous_identity_key: str
    read_back_identity_key: str
    mode: FromIdentityMode
    changed: bool
    verified: bool
    synthetic: bool = True


def select_from_identity(
    drafts: tuple[SyntheticDraft, ...],
    request: FromIdentityRequest,
    *,
    readiness: OutlookReadinessReport,
    identities: tuple[SyntheticFromIdentity, ...],
) -> tuple[tuple[SyntheticDraft, ...], FromIdentityResult]:
    """Select one explicitly authorized synthetic sender identity with read-back."""
    if not readiness.ready_for_readonly_discovery:
        raise ValueError("Outlook read-only discovery is not ready")
    current = next((item for item in drafts if item.draft_key == request.draft_key), None)
    if current is None or not current.synthetic:
        raise ValueError("synthetic draft_key not found")

    matches = tuple(item for item in identities if item.identity_key == request.identity_key)
    if len(matches) != 1:
        raise ValueError("From identity must resolve to exactly one candidate")
    identity = matches[0]
    if not identity.authorized:
        raise ValueError("From identity is not authorized")

    replacement = replace(current, from_identity_key=identity.identity_key)
    updated = tuple(
        replacement if item.draft_key == request.draft_key else item for item in drafts
    )
    read_back = next(item for item in updated if item.draft_key == request.draft_key)
    if read_back.from_identity_key != identity.identity_key:
        raise RuntimeError("synthetic read-back did not prove From identity selection")

    return updated, FromIdentityResult(
        draft_key=request.draft_key,
        previous_identity_key=current.from_identity_key,
        read_back_identity_key=read_back.from_identity_key,
        mode=identity.mode,
        changed=current.from_identity_key != identity.identity_key,
        verified=True,
    )


__all__ = [
    "FromIdentityMode",
    "FromIdentityRequest",
    "FromIdentityResult",
    "SyntheticFromIdentity",
    "select_from_identity",
]
