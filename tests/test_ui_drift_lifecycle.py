"""CORE-017 UI drift lifecycle acceptance tests."""

from __future__ import annotations

import pytest

from m365_mcp.capability_registry import default_capability_registry
from m365_mcp.effective_capabilities import (
    EffectiveCapabilityEvidence,
    EffectiveCapabilityState,
    project_effective_capabilities_by_capability,
)
from m365_mcp.ui_contract_store import UIContractFragment, UIContractSet
from m365_mcp.ui_drift import (
    UILifecycleEvent,
    UILifecycleState,
    transition_ui_lifecycle,
)


def _fragment(fragment_id: str, capability_keys: tuple[str, ...]) -> UIContractFragment:
    return UIContractFragment(
        fragment_id=fragment_id,
        fragment_version="0.1.0",
        scope="surface",
        application="planner",
        surface="planner-premium-web",
        capability_keys=capability_keys,
        attested=True,
        attestation_status="ATTESTED",
        selectors={
            f"{fragment_id}.selector": {"value": "stable", "status": "ATTESTED"}
        },
    )


def _contract_set() -> UIContractSet:
    return UIContractSet(
        set_version="0.1.0",
        legacy_version="0.1.0",
        fragments=(
            _fragment("planner.plan-surface", ("plans.read", "project_snapshot.read")),
            _fragment(
                "planner.task-surface",
                ("tasks.read", "buckets.read", "project_snapshot.read"),
            ),
        ),
    )


def _effective_evidence(attestation: object) -> EffectiveCapabilityEvidence:
    item = attestation
    return EffectiveCapabilityEvidence(
        authenticated=True,
        account_context_valid=True,
        ui_attested=item.attested,
        runtime_healthy=True,
        policy_allowed=True,
        license_available=True,
        live_evidence=True,
        ui_drifted=item.drifted,
        ui_stale=item.stale,
        ui_reattestation_required=item.reattestation_required,
    )


def test_closed_lifecycle_transitions_require_re_attestation_after_drift() -> None:
    state = transition_ui_lifecycle(
        UILifecycleState.HEALTHY,
        UILifecycleEvent.DRIFT_DETECTED,
    )
    assert state is UILifecycleState.DRIFTED
    with pytest.raises(ValueError, match="invalid UI lifecycle transition"):
        transition_ui_lifecycle(state, UILifecycleEvent.REATTESTATION_PASSED)

    state = transition_ui_lifecycle(state, UILifecycleEvent.REATTESTATION_REQUIRED)
    assert state is UILifecycleState.RE_ATTESTATION_REQUIRED
    state = transition_ui_lifecycle(state, UILifecycleEvent.REATTESTATION_PASSED)
    assert state is UILifecycleState.HEALTHY


def test_stale_fragment_only_degrades_dependent_capabilities() -> None:
    contract_set = _contract_set()
    registry = default_capability_registry()
    lifecycle = {"planner.task-surface": UILifecycleState.STALE}
    attestations = {
        name: contract_set.attestation_for_capability(
            "planner",
            name,
            lifecycle_by_fragment=lifecycle,
        )
        for name in registry.capability_names("planner")
    }
    evidence = {
        name: _effective_evidence(attestation)
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
    assert by_name["tasks.read"].reasons == ("UI_EVIDENCE_STALE",)


def test_re_attestation_required_withdraws_support_without_marking_drift() -> None:
    contract_set = _contract_set()
    attestation = contract_set.attestation_for_capability(
        "planner",
        "tasks.read",
        lifecycle_by_fragment={
            "planner.task-surface": UILifecycleState.RE_ATTESTATION_REQUIRED
        },
    )
    assert attestation.attested is False
    assert attestation.drifted is False
    assert attestation.stale is False
    assert attestation.reattestation_required is True
    assert attestation.reasons == (
        "UI_FRAGMENT_RE_ATTESTATION_REQUIRED:planner.task-surface",
    )


def test_lifecycle_overlay_cannot_promote_unattested_fragment() -> None:
    fragment = _fragment("planner.task-surface", ("tasks.read",))
    unattested = UIContractFragment(
        fragment_id=fragment.fragment_id,
        fragment_version=fragment.fragment_version,
        scope=fragment.scope,
        application=fragment.application,
        surface=fragment.surface,
        capability_keys=fragment.capability_keys,
        attested=False,
        attestation_status="UNVERIFIED_LIVE",
        selectors={
            "planner.task-surface.selector": {
                "value": None,
                "status": "UNVERIFIED_LIVE",
            }
        },
    )
    contract_set = UIContractSet("0.1.0", "0.1.0", (unattested,))
    attestation = contract_set.attestation_for_capability(
        "planner",
        "tasks.read",
        lifecycle_by_fragment={"planner.task-surface": UILifecycleState.HEALTHY},
    )
    assert attestation.attested is False
    assert attestation.reasons == (
        "UI_FRAGMENT_HEALTHY_WITHOUT_ATTESTATION:planner.task-surface",
    )


def test_unknown_fragment_lifecycle_overlay_fails_closed() -> None:
    with pytest.raises(ValueError, match="unknown fragment"):
        _contract_set().attestation_for_capability(
            "planner",
            "tasks.read",
            lifecycle_by_fragment={"outlook.mail": UILifecycleState.DRIFTED},
        )
