"""Planner capability evidence projected from scoped registry and effective evidence."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from m365_mcp.capability_registry import default_capability_registry
from m365_mcp.effective_capabilities import (
    EffectiveCapabilityEvidence,
    project_effective_capabilities,
)

from .auth import AuthState
from .contracts import load_contract
from .ui_contract import load_status


@dataclass(frozen=True)
class CapabilityEvidence:
    """Compatibility view for one Planner capability."""

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


def _account_context_valid(account_context: dict[str, Any]) -> bool:
    return (
        account_context.get("account_kind") == "work_or_school"
        and account_context.get("profile") == "professional-isolated"
    )


def build_capabilities(
    *,
    auth_evidence: dict[str, Any] | None = None,
    account_context: dict[str, Any] | None = None,
    license_evidence: dict[str, Any] | None = None,
    runtime_ok: bool = True,
    policy_allowed: bool = True,
    live_evidence: bool = False,
) -> dict[str, Any]:
    """Build capability compatibility output plus effective scoped projection."""
    ui = load_status()
    auth_evidence = auth_evidence or {}
    account_context = account_context or {}
    license_evidence = license_evidence or {}

    evidence = EffectiveCapabilityEvidence(
        authenticated=(
            str(auth_evidence.get("state", AuthState.UNKNOWN.value))
            == AuthState.AUTHENTICATED.value
        ),
        account_context_valid=_account_context_valid(account_context),
        ui_attested=ui.attested,
        runtime_healthy=runtime_ok,
        policy_allowed=policy_allowed,
        license_available=bool(license_evidence.get("premium_detected")),
        live_evidence=live_evidence,
    )
    registry = default_capability_registry()
    effective = project_effective_capabilities(
        registry,
        application="planner",
        evidence=evidence,
    )
    effective_by_name = {item.definition.capability: item for item in effective}

    rows = [
        CapabilityEvidence(
            capability=name,
            tenant_license_availability=(
                "OBSERVED" if evidence.license_available else "UNVERIFIED_LIVE"
            ),
            ui_observed="OBSERVED" if ui.attested else "UNVERIFIED_LIVE",
            ui_contract_status=ui.attestation_status,
            read_attestation=(
                "YES"
                if effective_by_name[name].state.value == "READ_SUPPORTED"
                else "NO"
            ),
            mutation_attestation="NO",
            support_level=effective_by_name[name].state.value,
            notes="Graph API availability is not an input to support state.",
        )
        for name in registry.capability_names("planner")
    ]
    manifest = load_contract("capability_manifest")
    return {
        "contract_version": manifest.get("contract_version", "0.1.0"),
        "evidence_dimensions": manifest.get("evidence_dimensions", []),
        "runtime_ok": runtime_ok,
        "graph_api_used": False,
        "support_levels": list(SUPPORT_LEVELS),
        "capabilities": [asdict(row) for row in rows],
        "effective_projection": [item.to_dict() for item in effective],
    }
