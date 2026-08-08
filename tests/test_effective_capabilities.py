"""CORE-012 effective capability projection acceptance tests."""

from __future__ import annotations

from m365_mcp.capability_registry import default_capability_registry
from m365_mcp.effective_capabilities import (
    EffectiveCapabilityEvidence,
    EffectiveCapabilityState,
    project_effective_capabilities,
)
from planner_mcp.auth import AuthState
from planner_mcp.capabilities import build_capabilities


def _evidence(**overrides: bool) -> EffectiveCapabilityEvidence:
    values = {
        "authenticated": True,
        "account_context_valid": True,
        "ui_attested": True,
        "runtime_healthy": True,
        "policy_allowed": True,
        "license_available": True,
        "live_evidence": True,
    }
    values.update(overrides)
    return EffectiveCapabilityEvidence(**values)


def test_all_required_live_evidence_promotes_read_support() -> None:
    projected = project_effective_capabilities(
        default_capability_registry(),
        application="planner",
        evidence=_evidence(),
    )
    assert len(projected) == 11
    assert all(item.state is EffectiveCapabilityState.READ_SUPPORTED for item in projected)
    assert all(item.supported for item in projected)


def test_registry_plus_mock_evidence_never_claims_live_support() -> None:
    projected = project_effective_capabilities(
        default_capability_registry(),
        application="planner",
        evidence=_evidence(live_evidence=False),
    )
    assert all(item.state is EffectiveCapabilityState.UNVERIFIED_LIVE for item in projected)
    assert all("LIVE_EVIDENCE_ABSENT" in item.reasons for item in projected)


def test_policy_or_runtime_failure_blocks_effective_support() -> None:
    registry = default_capability_registry()
    policy = project_effective_capabilities(
        registry,
        application="planner",
        evidence=_evidence(policy_allowed=False),
    )
    runtime = project_effective_capabilities(
        registry,
        application="planner",
        evidence=_evidence(runtime_healthy=False),
    )
    assert all(item.state is EffectiveCapabilityState.BLOCKED for item in policy)
    assert all(item.reasons == ("POLICY_DENIED",) for item in policy)
    assert all(item.state is EffectiveCapabilityState.BLOCKED for item in runtime)
    assert all(item.reasons == ("RUNTIME_UNHEALTHY",) for item in runtime)


def test_missing_auth_account_ui_or_license_remains_unverified() -> None:
    for field, reason in (
        ("authenticated", "AUTH_NOT_ATTESTED"),
        ("account_context_valid", "ACCOUNT_CONTEXT_UNVERIFIED"),
        ("ui_attested", "UI_NOT_ATTESTED"),
        ("license_available", "LICENSE_UNVERIFIED"),
    ):
        projected = project_effective_capabilities(
            default_capability_registry(),
            application="planner",
            evidence=_evidence(**{field: False}),
        )
        assert all(item.state is EffectiveCapabilityState.UNVERIFIED_LIVE for item in projected)
        assert all(reason in item.reasons for item in projected)


def test_planner_compatibility_output_keeps_keys_and_mock_not_supported() -> None:
    result = build_capabilities(
        auth_evidence={"state": AuthState.AUTHENTICATED.value},
        account_context={
            "account_kind": "work_or_school",
            "profile": "professional-isolated",
        },
        license_evidence={"premium_detected": True},
        runtime_ok=True,
        policy_allowed=True,
        live_evidence=False,
    )
    assert len(result["capabilities"]) == 11
    assert len(result["effective_projection"]) == 11
    assert all(item["support_level"] == "UNVERIFIED_LIVE" for item in result["capabilities"])
    assert all(item["read_attestation"] == "NO" for item in result["capabilities"])
    assert all(not item["supported"] for item in result["effective_projection"])


def test_live_mode_flag_without_explicit_live_ui_provenance_is_not_support() -> None:
    result = build_capabilities(
        auth_evidence={"state": AuthState.AUTHENTICATED.value},
        account_context={
            "account_kind": "work_or_school",
            "profile": "professional-isolated",
        },
        license_evidence={"premium_detected": True},
        runtime_ok=True,
        policy_allowed=True,
        live_evidence=True,
    )
    assert all(item["support_level"] == "UNVERIFIED_LIVE" for item in result["capabilities"])
    assert all(
        "LIVE_EVIDENCE_ABSENT" in item["reasons"]
        for item in result["effective_projection"]
    )
