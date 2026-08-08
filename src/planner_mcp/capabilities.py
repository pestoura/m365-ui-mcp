"""Dynamic capability model driven by real evidence, never by Graph availability."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

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

_CAPABILITIES = (
    "plans.read",
    "tasks.read",
    "buckets.read",
    "dependencies.read",
    "scheduling.read",
    "goals.read",
    "sprints.read",
    "resources.read",
    "custom_fields.read",
    "portfolios.read",
    "project_snapshot.read",
)


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
    """Build the capability manifest from tenant/license/UI/UIContract/runtime evidence."""
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
        for name in _CAPABILITIES
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
