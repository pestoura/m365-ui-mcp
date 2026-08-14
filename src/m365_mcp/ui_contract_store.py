"""Validated fragmented UIContract storage and dependency-aware attestation."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from m365_mcp.capability_registry import default_capability_registry
from m365_mcp.contracts import contracts_dir
from m365_mcp.locators import locator_plan_from_metadata
from m365_mcp.ui_drift import UILifecycleState

_ALLOWED_SCOPES = frozenset({"common", "application", "surface"})
_ALLOWED_ATTESTATION = frozenset({"ATTESTED", "UNVERIFIED_LIVE", "DRIFTED"})


@dataclass(frozen=True)
class UIContractFragment:
    """One validated UIContract storage fragment."""

    fragment_id: str
    fragment_version: str
    scope: str
    application: str | None
    surface: str | None
    capability_keys: tuple[str, ...]
    attested: bool
    attestation_status: str
    selectors: dict[str, Any]

    @property
    def drifted(self) -> bool:
        """Return whether fragment or selector evidence reports UI drift."""
        return self.attestation_status == "DRIFTED" or any(
            metadata.get("status") == "DRIFTED" for metadata in self.selectors.values()
        )

    @property
    def effectively_attested(self) -> bool:
        """Require fragment and every selector to be explicitly attested."""
        return (
            not self.drifted
            and self.attested
            and self.attestation_status == "ATTESTED"
            and all(
                metadata.get("status") == "ATTESTED"
                for metadata in self.selectors.values()
            )
        )

    def canonical_payload(self) -> dict[str, object]:
        """Return contract content only; never filesystem or runtime/session metadata."""
        return {
            "fragment_id": self.fragment_id,
            "fragment_version": self.fragment_version,
            "scope": self.scope,
            "application": self.application,
            "surface": self.surface,
            "capability_keys": list(self.capability_keys),
            "attested": self.attested,
            "attestation_status": self.attestation_status,
            "selectors": self.selectors,
        }


@dataclass(frozen=True)
class CapabilityUIAttestation:
    """Dependency-aware UI attestation for one semantic capability."""

    application: str
    capability: str
    dependency_fragments: tuple[str, ...]
    attested: bool
    drifted: bool
    reasons: tuple[str, ...]
    stale: bool = False
    reattestation_required: bool = False
    lifecycle_states: tuple[tuple[str, str], ...] = ()

    def to_dict(self) -> dict[str, object]:
        return {
            "application": self.application,
            "capability": self.capability,
            "dependency_fragments": list(self.dependency_fragments),
            "attested": self.attested,
            "drifted": self.drifted,
            "stale": self.stale,
            "reattestation_required": self.reattestation_required,
            "lifecycle_states": [
                {"fragment_id": fragment_id, "state": state}
                for fragment_id, state in self.lifecycle_states
            ],
            "reasons": list(self.reasons),
        }


@dataclass(frozen=True)
class UIContractSet:
    """Deterministically ordered set of UIContract fragments."""

    set_version: str
    legacy_version: str
    fragments: tuple[UIContractFragment, ...]

    def selectors(self) -> dict[str, Any]:
        """Return the validated selector union in manifest order.

        Only the scalar contract fields (value, status) are projected. Structured
        ``locators`` plans remain source-controlled in the fragment documents under
        ``contracts/ui_fragments`` and are intentionally not surfaced into the flat
        legacy-equivalent selector view, keeping public tool schemas and the legacy
        contract compatibility projection unchanged.
        """
        merged: dict[str, Any] = {}
        for fragment in self.fragments:
            for name, metadata in fragment.selectors.items():
                if name in merged:
                    raise ValueError(f"duplicate UIContract selector: {name}")
                merged[name] = {
                    key: value
                    for key, value in metadata.items()
                    if key in ("value", "status")
                }
        return merged

    def canonical_payload(self) -> dict[str, object]:
        """Return the exact semantic contract set used to derive a digest."""
        return {
            "ui_contract_set_version": self.set_version,
            "legacy_ui_contract_version": self.legacy_version,
            "fragments": [fragment.canonical_payload() for fragment in self.fragments],
        }

    def digest(self) -> str:
        """Return deterministic SHA-256 identity for this exact contract set."""
        encoded = json.dumps(
            self.canonical_payload(),
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
        return f"sha256:{hashlib.sha256(encoded).hexdigest()}"

    def fragments_for_capability(
        self, application: str, capability: str
    ) -> tuple[UIContractFragment, ...]:
        """Return only fragments explicitly declared as capability dependencies."""
        return tuple(
            fragment
            for fragment in self.fragments
            if fragment.application == application
            and capability in fragment.capability_keys
        )

    def _normalize_lifecycle_overlay(
        self,
        lifecycle_by_fragment: Mapping[str, UILifecycleState | str] | None,
    ) -> dict[str, UILifecycleState]:
        if lifecycle_by_fragment is None:
            return {}
        known = {fragment.fragment_id for fragment in self.fragments}
        unknown = set(lifecycle_by_fragment) - known
        if unknown:
            raise ValueError("UI lifecycle overlay references unknown fragment")
        normalized: dict[str, UILifecycleState] = {}
        for fragment_id, raw_state in lifecycle_by_fragment.items():
            try:
                normalized[fragment_id] = UILifecycleState(raw_state)
            except ValueError as exc:
                raise ValueError("UI lifecycle overlay contains invalid state") from exc
        return normalized

    def attestation_for_capability(
        self,
        application: str,
        capability: str,
        *,
        lifecycle_by_fragment: Mapping[str, UILifecycleState | str] | None = None,
    ) -> CapabilityUIAttestation:
        """Compute attestation without allowing unrelated fragments to degrade support."""
        dependencies = self.fragments_for_capability(application, capability)
        dependency_ids = tuple(fragment.fragment_id for fragment in dependencies)
        if not dependencies:
            return CapabilityUIAttestation(
                application=application,
                capability=capability,
                dependency_fragments=(),
                attested=False,
                drifted=False,
                reasons=("UI_DEPENDENCY_UNDECLARED",),
            )

        overlay = self._normalize_lifecycle_overlay(lifecycle_by_fragment)
        lifecycle: dict[str, UILifecycleState] = {}
        invalid_healthy: list[UIContractFragment] = []
        for fragment in dependencies:
            if fragment.drifted:
                lifecycle[fragment.fragment_id] = UILifecycleState.DRIFTED
                continue
            explicit = overlay.get(fragment.fragment_id)
            if explicit is UILifecycleState.HEALTHY and not fragment.effectively_attested:
                invalid_healthy.append(fragment)
                continue
            if explicit is not None:
                lifecycle[fragment.fragment_id] = explicit
            elif fragment.effectively_attested:
                lifecycle[fragment.fragment_id] = UILifecycleState.HEALTHY

        lifecycle_states = tuple(
            (fragment.fragment_id, lifecycle[fragment.fragment_id].value)
            for fragment in dependencies
            if fragment.fragment_id in lifecycle
        )

        if invalid_healthy:
            return CapabilityUIAttestation(
                application=application,
                capability=capability,
                dependency_fragments=dependency_ids,
                attested=False,
                drifted=False,
                reasons=tuple(
                    f"UI_FRAGMENT_HEALTHY_WITHOUT_ATTESTATION:{fragment.fragment_id}"
                    for fragment in invalid_healthy
                ),
                lifecycle_states=lifecycle_states,
            )

        drifted = tuple(
            fragment
            for fragment in dependencies
            if lifecycle.get(fragment.fragment_id) is UILifecycleState.DRIFTED
        )
        if drifted:
            return CapabilityUIAttestation(
                application=application,
                capability=capability,
                dependency_fragments=dependency_ids,
                attested=False,
                drifted=True,
                reasons=tuple(
                    f"UI_FRAGMENT_DRIFT:{fragment.fragment_id}" for fragment in drifted
                ),
                lifecycle_states=lifecycle_states,
            )

        reattestation = tuple(
            fragment
            for fragment in dependencies
            if lifecycle.get(fragment.fragment_id)
            is UILifecycleState.RE_ATTESTATION_REQUIRED
        )
        if reattestation:
            return CapabilityUIAttestation(
                application=application,
                capability=capability,
                dependency_fragments=dependency_ids,
                attested=False,
                drifted=False,
                reattestation_required=True,
                reasons=tuple(
                    f"UI_FRAGMENT_RE_ATTESTATION_REQUIRED:{fragment.fragment_id}"
                    for fragment in reattestation
                ),
                lifecycle_states=lifecycle_states,
            )

        stale = tuple(
            fragment
            for fragment in dependencies
            if lifecycle.get(fragment.fragment_id) is UILifecycleState.STALE
        )
        if stale:
            return CapabilityUIAttestation(
                application=application,
                capability=capability,
                dependency_fragments=dependency_ids,
                attested=False,
                drifted=False,
                stale=True,
                reasons=tuple(
                    f"UI_FRAGMENT_STALE:{fragment.fragment_id}" for fragment in stale
                ),
                lifecycle_states=lifecycle_states,
            )

        unattested = tuple(
            fragment for fragment in dependencies if not fragment.effectively_attested
        )
        if unattested:
            return CapabilityUIAttestation(
                application=application,
                capability=capability,
                dependency_fragments=dependency_ids,
                attested=False,
                drifted=False,
                reasons=tuple(
                    f"UI_FRAGMENT_UNATTESTED:{fragment.fragment_id}"
                    for fragment in unattested
                ),
                lifecycle_states=lifecycle_states,
            )

        return CapabilityUIAttestation(
            application=application,
            capability=capability,
            dependency_fragments=dependency_ids,
            attested=True,
            drifted=False,
            reasons=("UI_DEPENDENCIES_ATTESTED",),
            lifecycle_states=lifecycle_states,
        )


def _read_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"UIContract document must be an object: {path.name}")
    return data


def _fragment_path(root: Path, relative: str) -> Path:
    candidate = Path(relative)
    if candidate.is_absolute() or ".." in candidate.parts:
        raise ValueError("UIContract fragment path must remain inside contracts directory")
    if not candidate.parts or candidate.parts[0] != "ui_fragments":
        raise ValueError("UIContract fragments must live under ui_fragments/")
    return root / candidate


def _load_fragment(root: Path, expected_id: str, relative: str) -> UIContractFragment:
    path = _fragment_path(root, relative)
    document = _read_json(path)
    fragment_id = str(document.get("fragment_id", "")).strip()
    fragment_version = str(document.get("fragment_version", "")).strip()
    scope = str(document.get("scope", "")).strip()
    application = document.get("application")
    surface = document.get("surface")
    capability_keys = document.get("capability_keys", [])
    attestation_status = str(document.get("attestation_status", "UNVERIFIED_LIVE"))
    selectors = document.get("selectors")

    if not fragment_id or fragment_id != expected_id:
        raise ValueError("UIContract fragment id does not match manifest")
    if not fragment_version:
        raise ValueError(f"UIContract fragment {fragment_id} has no version")
    if scope not in _ALLOWED_SCOPES:
        raise ValueError(f"UIContract fragment {fragment_id} has invalid scope")
    if application is not None and not isinstance(application, str):
        raise ValueError(f"UIContract fragment {fragment_id} has invalid application")
    if surface is not None and not isinstance(surface, str):
        raise ValueError(f"UIContract fragment {fragment_id} has invalid surface")
    if scope == "common" and (application is not None or surface is not None):
        raise ValueError("common UIContract fragment cannot bind app or surface")
    if scope == "application" and (not application or surface is not None):
        raise ValueError("application UIContract fragment requires app and no surface")
    if scope == "surface" and (not application or not surface):
        raise ValueError("surface UIContract fragment requires app and surface")
    if not isinstance(capability_keys, list) or any(
        not isinstance(key, str)
        or not key
        or key != key.strip()
        or any(char.isspace() for char in key)
        or "." not in key
        for key in capability_keys
    ):
        raise ValueError(f"UIContract fragment {fragment_id} has invalid capability keys")
    if len(capability_keys) != len(set(capability_keys)):
        raise ValueError(f"UIContract fragment {fragment_id} has duplicate capability keys")
    if scope == "common" and capability_keys:
        raise ValueError("common UIContract fragments cannot own app capability dependencies")
    if application:
        registry = default_capability_registry()
        unknown = [
            key for key in capability_keys if not registry.has_capability(application, key)
        ]
        if unknown:
            raise ValueError(
                f"UIContract fragment {fragment_id} references unknown capability"
            )
    if attestation_status not in _ALLOWED_ATTESTATION:
        raise ValueError(f"UIContract fragment {fragment_id} has invalid attestation status")
    if not isinstance(selectors, dict) or not selectors:
        raise ValueError(f"UIContract fragment {fragment_id} must contain selectors")
    for name, metadata in selectors.items():
        if not isinstance(name, str) or not name.strip() or not isinstance(metadata, dict):
            raise ValueError(f"UIContract fragment {fragment_id} contains invalid selector")
        if metadata.get("status") not in _ALLOWED_ATTESTATION:
            raise ValueError(f"UIContract fragment {fragment_id} has invalid selector status")
        locator_plan_from_metadata(name, metadata)

    return UIContractFragment(
        fragment_id=fragment_id,
        fragment_version=fragment_version,
        scope=scope,
        application=application,
        surface=surface,
        capability_keys=tuple(capability_keys),
        attested=bool(document.get("attested", False)),
        attestation_status=attestation_status,
        selectors=selectors,
    )


def load_ui_contract_set(root: Path | None = None) -> UIContractSet:
    """Load the manifest and all fragments, rejecting malformed or duplicate data."""
    contract_root = root or contracts_dir()
    manifest = _read_json(contract_root / "ui_contract_set.json")
    set_version = str(manifest.get("ui_contract_set_version", "")).strip()
    legacy_version = str(manifest.get("legacy_ui_contract_version", "")).strip()
    entries = manifest.get("fragments")

    if not set_version or not legacy_version:
        raise ValueError("UIContract set and legacy versions are required")
    if not isinstance(entries, list) or not entries:
        raise ValueError("UIContract set must declare at least one fragment")

    seen_ids: set[str] = set()
    fragments: list[UIContractFragment] = []
    selector_owner: dict[str, str] = {}
    for entry in entries:
        if not isinstance(entry, dict):
            raise ValueError("UIContract manifest entries must be objects")
        fragment_id = str(entry.get("fragment_id", "")).strip()
        relative = str(entry.get("path", "")).strip()
        if not fragment_id or fragment_id in seen_ids:
            raise ValueError("UIContract fragment ids must be non-empty and unique")
        if not relative:
            raise ValueError(f"UIContract fragment {fragment_id} has no path")
        fragment = _load_fragment(contract_root, fragment_id, relative)
        for selector in fragment.selectors:
            if selector in selector_owner:
                owner = selector_owner[selector]
                raise ValueError(
                    f"duplicate UIContract selector {selector}: {owner} and {fragment_id}"
                )
            selector_owner[selector] = fragment_id
        seen_ids.add(fragment_id)
        fragments.append(fragment)

    return UIContractSet(
        set_version=set_version,
        legacy_version=legacy_version,
        fragments=tuple(fragments),
    )


__all__ = [
    "CapabilityUIAttestation",
    "UIContractFragment",
    "UIContractSet",
    "load_ui_contract_set",
]
