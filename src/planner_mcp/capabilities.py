"""Dynamic Planner capability evidence projected from the scoped M365 registry."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from m365_mcp.capability_registry import default_capability_registry

from .contracts import load_contract
from .ui_contract import load_status


@dataclass(frozen=True)
class CapabilityEvidence:
    """Evidence tuple for one Planner capability."""

    capability: str
    tenant_license_availability: str
    ui_observed: str
    ui_contract_status: str
    read_attestation: str
    mutation_attestation: str
    support_level: str
    notes: str


SUPPORT_LEVELS = (
    "UNVERIFIED_LIVE",
    "DISCOVERED",
    "READ_SUPPORTED",
    "MUTATION_SUPPORTED",
    "DEGRADED",
    "BLOCKED",
    "OUT_OF_SCOPE",
)


def _planner_capability_names() -> tuple[str, ...]:
    return default_capability_registry().capability_names("planner")


def _support_level(ui_attested: bool, license_known: bool, runtime_ok: bool) -> str:
    """Return only evidence-backed CAP-030 support states."""
    if not runtime_ok:
        return "BLOCKED"
    if ui_attested and license_known:
        return "READ_SUPPORTED"
    return "UNVERIFIED_LIVE"


def build_capabilities(
    *, license_evidence: dict[str, Any] | None = None, runtime_ok: bool = True
) -> dict[str, Any]:
    """Build the Planner capability view from scoped definitions plus evidence."""
    ui = load_status()
    license_evidence = license_evidence or {}
    license_known = bool(license_evidence.get("premium_detected"))
    rows = [
        CapabilityEvidence(
            capability=name,
            tenant_license_availability=(
                "OBSERVED" if license_known else "UNVERIFIED_LIVE"
            ),
            ui_observed="OBSERVED" if ui.attested else "UNVERIFIED_LIVE",
            ui_contract_status=ui.attestation_status,
            read_attestation="YES" if ui.attested else "NO",
            mutation_attestation="NO",
            support_level=_support_level(ui.attested, license_known, runtime_ok),
            notes="Graph API availability is not an input to support state.",
        )
        for name in _planner_capability_names()
    ]
    manifest = load_contract("capability_manifest")
    return {
        "contract_version": manifest.get("contract_version", "0.1.0"),
        "evidence_dimensions": manifest.get("evidence_dimensions", []),
        "runtime_ok": runtime_ok,
        "graph_api_used": False,
        "support_levels": list(SUPPORT_LEVELS),
        "capabilities": [asdict(row) for row in rows],
    }
