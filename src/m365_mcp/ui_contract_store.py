"""Validated fragmented UIContract storage for Microsoft 365 UI surfaces."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from m365_mcp.contracts import contracts_dir

_ALLOWED_SCOPES = frozenset({"common", "application", "surface"})


@dataclass(frozen=True)
class UIContractFragment:
    """One validated UIContract storage fragment."""

    fragment_id: str
    fragment_version: str
    scope: str
    application: str | None
    surface: str | None
    attested: bool
    attestation_status: str
    selectors: dict[str, Any]


@dataclass(frozen=True)
class UIContractSet:
    """Deterministically ordered set of UIContract fragments."""

    set_version: str
    legacy_version: str
    fragments: tuple[UIContractFragment, ...]

    def selectors(self) -> dict[str, Any]:
        """Return the validated selector union in manifest order."""
        merged: dict[str, Any] = {}
        for fragment in self.fragments:
            for name, metadata in fragment.selectors.items():
                if name in merged:
                    raise ValueError(f"duplicate UIContract selector: {name}")
                merged[name] = metadata
        return merged


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
    if not isinstance(selectors, dict) or not selectors:
        raise ValueError(f"UIContract fragment {fragment_id} must contain selectors")
    for name, metadata in selectors.items():
        if not isinstance(name, str) or not name.strip() or not isinstance(metadata, dict):
            raise ValueError(f"UIContract fragment {fragment_id} contains invalid selector")

    return UIContractFragment(
        fragment_id=fragment_id,
        fragment_version=fragment_version,
        scope=scope,
        application=application,
        surface=surface,
        attested=bool(document.get("attested", False)),
        attestation_status=str(document.get("attestation_status", "UNVERIFIED_LIVE")),
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


__all__ = ["UIContractFragment", "UIContractSet", "load_ui_contract_set"]
