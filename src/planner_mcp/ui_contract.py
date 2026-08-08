"""UIContract loading and validation.

Selectors are never invented: every entry must carry an attestation record that references
captured evidence (ADR-007). A selector without attestation, or with attestation but no
usable locator, is a fail-closed condition — not a warning.

Dependency-free by design, matching ``planner_mcp.contracts``.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

CONTRACT_ROOT = "browser/selectors"

SELECTOR_ID_RE = re.compile(r"^[a-z0-9]+(?:\.[a-z0-9_]+)+$")
CAPTURED_AT_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
EVIDENCE_HASH_RE = re.compile(r"^sha256:[0-9a-f]{64}$")


class UIContractError(ValueError):
    """Raised when a UIContract document violates its schema."""


class UIDriftError(RuntimeError):
    """Raised when the observed UI no longer matches the attested contract."""


class UnattestedSelectorError(RuntimeError):
    """Raised when an operation would depend on a selector without evidence."""


@dataclass(frozen=True, slots=True)
class Attestation:
    """Evidence that a selector was actually observed in a real UI."""

    captured_at: str
    evidence_hash: str
    evidence_ref: str
    observer: str
    tenant_agnostic: bool = True

    def __post_init__(self) -> None:
        if not CAPTURED_AT_RE.match(self.captured_at):
            raise UIContractError(f"invalid captured_at: {self.captured_at!r}")
        if not EVIDENCE_HASH_RE.match(self.evidence_hash):
            raise UIContractError(f"invalid evidence_hash: {self.evidence_hash!r}")
        if not self.evidence_ref.strip():
            raise UIContractError("evidence_ref must not be empty")
        if not self.observer.strip():
            raise UIContractError("observer must not be empty")


@dataclass(frozen=True, slots=True)
class Selector:
    """One addressable UI element.

    ``role`` + ``name`` is the preferred locator strategy; ``test_id`` is second; raw ``css``
    is a last-resort fallback and is only ever usable together with an attestation record.
    """

    id: str
    description: str
    role: str | None = None
    name: str | None = None
    test_id: str | None = None
    css: str | None = None
    fallbacks: tuple[str, ...] = ()
    attestation: Attestation | None = None

    def __post_init__(self) -> None:
        if not SELECTOR_ID_RE.match(self.id):
            raise UIContractError(f"invalid selector id: {self.id!r}")
        if not self.description.strip():
            raise UIContractError(f"{self.id}: description must not be empty")

    def is_attested(self) -> bool:
        return self.attestation is not None

    def is_addressable(self) -> bool:
        return bool(self.role or self.test_id or self.css)

    def is_usable(self) -> bool:
        """Usable only when the selector is both addressable and attested."""
        return self.is_addressable() and self.is_attested()


@dataclass(frozen=True, slots=True)
class UIContract:
    version: str
    surface: str
    selectors: tuple[Selector, ...] = field(default=())

    def __post_init__(self) -> None:
        if not self.version.strip():
            raise UIContractError("contract version must not be empty")
        if not self.surface.strip():
            raise UIContractError("contract surface must not be empty")
        ids = [s.id for s in self.selectors]
        if len(ids) != len(set(ids)):
            raise UIContractError("duplicate selector ids in contract")

    def unattested(self) -> tuple[Selector, ...]:
        return tuple(s for s in self.selectors if not s.is_attested())

    def unusable(self) -> tuple[Selector, ...]:
        return tuple(s for s in self.selectors if not s.is_usable())

    def coverage(self) -> float:
        if not self.selectors:
            return 0.0
        return len([s for s in self.selectors if s.is_attested()]) / len(self.selectors)

    def get(self, selector_id: str) -> Selector:
        """Resolve a selector, failing closed (ADR-007).

        An unknown id and an unattested/unaddressable selector are the same class of
        failure: the operation must refuse rather than guess.
        """
        for selector in self.selectors:
            if selector.id == selector_id:
                return require_usable(selector)
        raise UnattestedSelectorError(f"selector {selector_id!r} is not present in the UIContract")


def require_usable(selector: Selector) -> Selector:
    """Fail closed on any selector that is not both addressable and attested."""
    if not selector.is_usable():
        raise UnattestedSelectorError(
            f"selector {selector.id!r} is not usable: missing locator or attestation"
        )
    return selector


def load_contract(payload: Any) -> UIContract:
    """Validate a parsed contract document. Parsing (YAML/JSON) is the caller's job."""
    if not isinstance(payload, dict):
        raise UIContractError("contract document must be a mapping")

    unknown = set(payload) - {"version", "surface", "selectors"}
    if unknown:
        raise UIContractError(f"unknown contract keys: {sorted(unknown)}")

    raw_selectors = payload.get("selectors") or []
    if not isinstance(raw_selectors, list):
        raise UIContractError("selectors must be a list")

    selectors: list[Selector] = []
    for raw in raw_selectors:
        if not isinstance(raw, dict):
            raise UIContractError("each selector must be a mapping")
        unknown_fields = set(raw) - {
            "id",
            "description",
            "role",
            "name",
            "test_id",
            "css",
            "fallbacks",
            "attestation",
        }
        if unknown_fields:
            raise UIContractError(f"unknown selector keys: {sorted(unknown_fields)}")

        raw_attestation = raw.get("attestation")
        attestation: Attestation | None = None
        if raw_attestation is not None:
            if not isinstance(raw_attestation, dict):
                raise UIContractError(f"{raw.get('id')}: attestation must be a mapping")
            attestation = Attestation(
                captured_at=str(raw_attestation.get("captured_at", "")),
                evidence_hash=str(raw_attestation.get("evidence_hash", "")),
                evidence_ref=str(raw_attestation.get("evidence_ref", "")),
                observer=str(raw_attestation.get("observer", "")),
                tenant_agnostic=bool(raw_attestation.get("tenant_agnostic", True)),
            )

        selectors.append(
            Selector(
                id=str(raw.get("id", "")),
                description=str(raw.get("description", "")),
                role=raw.get("role"),
                name=raw.get("name"),
                test_id=raw.get("test_id"),
                css=raw.get("css"),
                fallbacks=tuple(raw.get("fallbacks") or ()),
                attestation=attestation,
            )
        )

    return UIContract(
        version=str(payload.get("version", "")),
        surface=str(payload.get("surface", "")),
        selectors=tuple(selectors),
    )


__all__ = [
    "CONTRACT_ROOT",
    "Attestation",
    "Selector",
    "UIContract",
    "UIContractError",
    "UIDriftError",
    "UnattestedSelectorError",
    "load_contract",
    "require_usable",
]
