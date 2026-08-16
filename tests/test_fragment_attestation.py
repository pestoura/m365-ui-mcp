"""CORE-014 per-fragment attestation acceptance tests."""

from __future__ import annotations

from m365_mcp.capability_registry import default_capability_registry
from m365_mcp.effective_capabilities import (
    EffectiveCapabilityEvidence,
    EffectiveCapabilityState,
    project_effective_capabilities_by_capability,
)
from m365_mcp.ui_contract_store import UIContractFragment, UIContractSet


def _fragment(
    fragment_id: str,
    capability_keys: tuple[str, ...],
    *,
    status: str = "ATTESTED",
) -> UIContractFragment:
    return UIContractFragment(
        fragment_id=fragment_id,
        fragment_version="0.1.0",
        scope="surface",
        application="planner",
        surface="planner-premium-web",
        capability_keys=capability_keys,
        attested=status == "ATTESTED",
        attestation_status=status,
        selectors={
            f"{fragment_id}.selector": {"value": "stable", "status": status}
        },
    )


def _base_evidence(
    *, ui_attested: bool, ui_drifted: bool, live_read_path: bool = False
) -> EffectiveCapabilityEvidence:
    return EffectiveCapabilityEvidence(
        authenticated=True,
        account_context_valid=True,
        ui_attested=ui_attested,
        runtime_healthy=True,
        policy_allowed=True,
        license_available=True,
        live_evidence=True,
        ui_drifted=ui_drifted,
        live_read_path=live_read_path,
    )


def test_one_fragment_drift_only_degrades_dependent_capabilities() -> None:
    contract_set = UIContractSet(
        set_version="0.1.0",
        legacy_version="0.1.0",
        fragments=(
            _fragment("planner.plan-surface", ("plans.read", "project_snapshot.read")),
            _fragment(
                "planner.task-surface",
                ("tasks.read", "buckets.read", "project_snapshot.read"),
                status="DRIFTED",
            ),
        ),
    )
    registry = default_capability_registry()
    attestations = {
        name: contract_set.attestation_for_capability("planner", name)
        for name in registry.capability_names("planner")
    }
    evidence = {
        name: _base_evidence(
            ui_attested=attestation.attested,
            ui_drifted=attestation.drifted,
            live_read_path=name in {"plans.read", "tasks.read", "project_snapshot.read"},
        )
        for name, attestation in attestations.items()
    }
    projected = project_effective_capabilities_by_capability(
        registry,
        application="planner",
        evidence_by_capability=evidence,
    )
    by_name = {item.definition.capability: item for item in projected}

    assert by_name["plans.read"].state is EffectiveCapabilityState.READ_SUPPORTED
    assert by_name["tasks.read"].state is EffectiveCapabilityState.DEGRADED
    assert by_name["buckets.read"].state is EffectiveCapabilityState.DEGRADED
    assert by_name["project_snapshot.read"].state is EffectiveCapabilityState.DEGRADED
    assert by_name["dependencies.read"].state is EffectiveCapabilityState.UNVERIFIED_LIVE
    assert attestations["dependencies.read"].reasons == ("UI_DEPENDENCY_UNDECLARED",)


def test_unattested_fragment_does_not_degrade_unrelated_capability() -> None:
    contract_set = UIContractSet(
        set_version="0.1.0",
        legacy_version="0.1.0",
        fragments=(
            _fragment("planner.plan-surface", ("plans.read",)),
            _fragment("planner.task-surface", ("tasks.read",), status="UNVERIFIED_LIVE"),
        ),
    )
    plans = contract_set.attestation_for_capability("planner", "plans.read")
    tasks = contract_set.attestation_for_capability("planner", "tasks.read")

    assert plans.attested is True
    assert plans.drifted is False
    assert tasks.attested is False
    assert tasks.drifted is False
    assert tasks.reasons == ("UI_FRAGMENT_UNATTESTED:planner.task-surface",)


def test_projector_requires_exact_capability_evidence_surface() -> None:
    registry = default_capability_registry()
    evidence = {
        "plans.read": _base_evidence(ui_attested=True, ui_drifted=False),
    }
    try:
        project_effective_capabilities_by_capability(
            registry,
            application="planner",
            evidence_by_capability=evidence,
        )
    except ValueError as exc:
        assert "exact registry surface" in str(exc)
    else:
        raise AssertionError("incomplete capability evidence map must fail closed")


def test_shipped_fragment_dependencies_are_conservative() -> None:
    from m365_mcp.ui_contract_store import load_ui_contract_set

    contract_set = load_ui_contract_set()
    assert tuple(
        fragment.fragment_id
        for fragment in contract_set.fragments_for_capability("planner", "plans.read")
    ) == ("planner.plan-surface",)
    assert tuple(
        fragment.fragment_id
        for fragment in contract_set.fragments_for_capability("planner", "tasks.read")
    ) == ("planner.task-surface",)
    assert tuple(
        fragment.fragment_id
        for fragment in contract_set.fragments_for_capability(
            "planner", "project_snapshot.read"
        )
    ) == ("planner.plan-surface", "planner.task-surface")
    assert contract_set.fragments_for_capability("planner", "dependencies.read") == ()
