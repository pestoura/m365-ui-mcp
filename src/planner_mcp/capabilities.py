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
    "unsupported",
    "planned",
    "read_unattested",
    "read_attested",
    "mutation_attested",
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


def _support_level(ui_attested: bool, license_known: bool) -> str:
    if not license_known:
        return "planned"
    return "read_attested" if ui_attested else "read_unattested"


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
                "planner_premium_detected" if license_known else "unknown_no_evidence"
            ),
            ui_observed="not_observed" if not ui.attested else "observed",
            ui_contract_status=ui.attestation_status,
            read_attestation="attested" if ui.attested else "unattested",
            mutation_attestation="not_implemented_0_1_0",
            support_level=_support_level(ui.attested, license_known),
            notes="Graph API availability is not an input to support level.",
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
