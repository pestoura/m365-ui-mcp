"""Tenant-neutral synthetic signature catalog management for OUT-073."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from m365_mcp.apps.outlook.draft_signature_mutations import SyntheticSignature
from m365_mcp.apps.outlook.readiness import OutlookReadinessReport


def _validate_token(name: str, value: str) -> None:
    if not value or value != value.strip() or any(char.isspace() for char in value):
        raise ValueError(f"{name} must be a non-empty semantic token")


class SignatureCatalogAction(StrEnum):
    CREATE = "CREATE"
    UPDATE = "UPDATE"
    DELETE = "DELETE"


@dataclass(frozen=True)
class SyntheticManagedSignature:
    signature_key: str
    body_text: str
    enabled: bool = True

    def __post_init__(self) -> None:
        _validate_token("signature_key", self.signature_key)
        if "\x00" in self.body_text:
            raise ValueError("body_text must not contain NUL")

    def to_projection(self) -> dict[str, object]:
        return {
            "signature_key": self.signature_key,
            "body_text": self.body_text,
            "enabled": self.enabled,
            "synthetic": True,
        }

    def to_draft_signature(self) -> SyntheticSignature:
        return SyntheticSignature(
            signature_key=self.signature_key,
            enabled=self.enabled,
        )


@dataclass(frozen=True)
class SignatureCatalogRequest:
    action: SignatureCatalogAction
    signature_key: str
    signature: SyntheticManagedSignature | None = None

    def __post_init__(self) -> None:
        _validate_token("signature_key", self.signature_key)
        if self.action in {SignatureCatalogAction.CREATE, SignatureCatalogAction.UPDATE}:
            if self.signature is None or self.signature.signature_key != self.signature_key:
                raise ValueError("CREATE/UPDATE requires a matching synthetic signature")
        elif self.signature is not None:
            raise ValueError("DELETE does not accept signature")

    def to_payload(self) -> dict[str, object]:
        return {
            "action": self.action.value,
            "signature_key": self.signature_key,
            "signature": (
                None if self.signature is None else self.signature.to_projection()
            ),
        }


@dataclass(frozen=True)
class SignatureCatalogResult:
    action: SignatureCatalogAction
    signature_key: str
    changed: bool
    read_back: SyntheticManagedSignature | None
    verified: bool
    synthetic: bool = True


def _find(
    catalog: tuple[SyntheticManagedSignature, ...],
    signature_key: str,
) -> SyntheticManagedSignature | None:
    matches = tuple(item for item in catalog if item.signature_key == signature_key)
    if len(matches) > 1:
        raise RuntimeError("synthetic signature catalog became ambiguous")
    return matches[0] if matches else None


def mutate_signature_catalog(
    catalog: tuple[SyntheticManagedSignature, ...],
    request: SignatureCatalogRequest,
    *,
    readiness: OutlookReadinessReport,
) -> tuple[tuple[SyntheticManagedSignature, ...], SignatureCatalogResult]:
    """Apply one synthetic signature catalog mutation with exact read-back."""
    if not readiness.ready_for_readonly_discovery:
        raise ValueError("Outlook read-only discovery is not ready")

    current = _find(catalog, request.signature_key)
    if request.action is SignatureCatalogAction.CREATE:
        if current is not None:
            raise ValueError("CREATE requires a new signature_key")
        assert request.signature is not None
        updated = catalog + (request.signature,)
        changed = True
    elif request.action is SignatureCatalogAction.UPDATE:
        if current is None:
            raise ValueError("UPDATE requires an existing signature_key")
        assert request.signature is not None
        updated = tuple(
            request.signature if item.signature_key == request.signature_key else item
            for item in catalog
        )
        changed = current != request.signature
    else:
        updated = tuple(
            item for item in catalog if item.signature_key != request.signature_key
        )
        changed = current is not None

    updated = tuple(sorted(updated, key=lambda item: item.signature_key))
    read_back = _find(updated, request.signature_key)
    expected = None if request.action is SignatureCatalogAction.DELETE else request.signature
    if read_back != expected:
        raise RuntimeError("synthetic read-back did not prove signature catalog state")

    return updated, SignatureCatalogResult(
        action=request.action,
        signature_key=request.signature_key,
        changed=changed,
        read_back=read_back,
        verified=True,
    )


__all__ = [
    "SignatureCatalogAction",
    "SignatureCatalogRequest",
    "SignatureCatalogResult",
    "SyntheticManagedSignature",
    "mutate_signature_catalog",
]
