"""Planner capability evidence projected from scoped registry and UI fragments."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from m365_mcp.capability_registry import default_capability_registry
from m365_mcp.effective_capabilities import (
    EffectiveCapabilityEvidence,
    project_effective_capabilities_by_capability,
)
from m365_mcp.ui_contract_store import load_ui_contract_set

from .auth import AuthState
from .contracts import load_contract


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


def _explicit_live_evidence_present(
    *,
    requested: bool,
    auth_evidence: dict[str, Any],
    account_context: dict[str, Any],
    license_evidence: dict[str, Any],
) -> bool:
    """Require explicit live-UI provenance; live mode alone is never evidence."""
    if not requested:
        return False
    evidence_sets = (auth_evidence, account_context, license_evidence)
    return all(
        str(item.get("evidence_source", "")).strip().lower() == "live_ui"
        for item in evidence_sets
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
    """Build compatibility output plus dependency-aware effective projection."""
    auth_evidence = auth_evidence or {}
    account_context = account_context or {}
    license_evidence = license_evidence or {}
    registry = default_capability_registry()
    contract_set = load_ui_contract_set()

    authenticated = (
        str(auth_evidence.get("state", AuthState.UNKNOWN.value))
        == AuthState.AUTHENTICATED.value
    )
    account_valid = _account_context_valid(account_context)
    license_available = bool(license_evidence.get("premium_detected"))
    explicit_live = _explicit_live_evidence_present(
        requested=live_evidence,
        auth_evidence=auth_evidence,
        account_context=account_context,
        license_evidence=license_evidence,
    )

    ui_attestation = {
        name: contract_set.attestation_for_capability("planner", name)
        for name in registry.capability_names("planner")
    }
    evidence_by_capability = {
        name: EffectiveCapabilityEvidence(
            authenticated=authenticated,
            account_context_valid=account_valid,
            ui_attested=attestation.attested,
            runtime_healthy=runtime_ok,
            policy_allowed=policy_allowed,
            license_available=license_available,
            live_evidence=explicit_live,
            ui_drifted=attestation.drifted,
        )
        for name, attestation in ui_attestation.items()
    }
    effective = project_effective_capabilities_by_capability(
        registry,
        application="planner",
        evidence_by_capability=evidence_by_capability,
    )
    effective_by_name = {item.definition.capability: item for item in effective}

    rows = [
        CapabilityEvidence(
            capability=name,
            tenant_license_availability=(
                "OBSERVED" if license_available else "UNVERIFIED_LIVE"
            ),
            ui_observed=(
                "OBSERVED" if ui_attestation[name].attested else "UNVERIFIED_LIVE"
            ),
            ui_contract_status=(
                "DRIFTED"
                if ui_attestation[name].drifted
                else "ATTESTED"
                if ui_attestation[name].attested
                else "UNVERIFIED_LIVE"
            ),
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
        "ui_contract_set_digest": contract_set.digest(),
        "evidence_dimensions": manifest.get("evidence_dimensions", []),
        "runtime_ok": runtime_ok,
        "graph_api_used": False,
        "support_levels": list(SUPPORT_LEVELS),
        "capabilities": [asdict(row) for row in rows],
        "effective_projection": [item.to_dict() for item in effective],
        "ui_fragment_attestation": [
            ui_attestation[name].to_dict()
            for name in registry.capability_names("planner")
        ],
    }
