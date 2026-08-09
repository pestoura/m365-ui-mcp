"""PLN-MIG-009 — Planner policy parity suite.

Asserts that no preserved Planner operation became less governed after the
generalized M365 platform extraction. Policy parity is a governance projection
only; it never attests live behavior.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from m365_mcp.apps.planner.policy_parity import (
    DECISION_STRENGTH,
    governance_regressions,
    policy_parity_digest,
    policy_parity_snapshot,
    policy_projection,
)
from m365_mcp.apps.planner.public_surface import PLANNER_PUBLIC_TOOL_NAMES
from m365_mcp.apps.planner.schemas import planner_semantic_schemas
from m365_mcp.capability_registry import default_capability_registry
from m365_mcp.config import Settings
from m365_mcp.effective_capabilities import (
    EffectiveCapabilityEvidence,
    EffectiveCapabilityState,
    project_effective_capabilities,
)
from m365_mcp.policy import Decision, evaluate
from m365_mcp.policy_scope import PolicyScope, canonical_policy_scope
from m365_mcp.tool_registry import MutationClass, default_tool_registry
from planner_mcp import policy as planner_policy

BASELINE_PATH = (
    Path(__file__).resolve().parents[1]
    / "tests"
    / "data"
    / "planner_policy_parity_baseline.json"
)

_FORBIDDEN_PROJECTION_KEYS = frozenset(
    {
        "token",
        "access_token",
        "refresh_token",
        "cookie",
        "cookies",
        "storage_state",
        "password",
        "state_path",
        "worker_base_url",
        "mailbox_address",
        "tenant_id",
        "upn",
    }
)


def _baseline() -> dict[str, Any]:
    payload: dict[str, Any] = json.loads(BASELINE_PATH.read_text(encoding="utf-8"))
    return payload


def test_baseline_covers_exact_preserved_public_abi() -> None:
    baseline = _baseline()

    assert tuple(baseline["tools"]) == PLANNER_PUBLIC_TOOL_NAMES
    assert len(baseline["tools"]) == 17
    assert baseline["live_support_claimed"] is False
    assert baseline["mode"] == "mock"
    assert tuple(baseline["governance"]) == PLANNER_PUBLIC_TOOL_NAMES


def test_projected_governance_matches_frozen_policy_baseline() -> None:
    snapshot = policy_parity_snapshot()
    baseline = _baseline()

    assert list(snapshot) == list(baseline["governance"])
    for tool in snapshot:
        assert snapshot[tool] == baseline["governance"][tool], f"policy drift in {tool}"
    assert policy_parity_digest(snapshot) == baseline["digest"]


def test_policy_projection_is_deterministic_across_repeated_evaluations() -> None:
    first = policy_parity_snapshot()
    second = policy_parity_snapshot()

    assert first == second
    assert policy_parity_digest(first) == policy_parity_digest(second)


def test_no_preserved_planner_tool_became_less_governed() -> None:
    baseline = _baseline()

    assert governance_regressions(policy_parity_snapshot(), baseline["governance"]) == ()


def test_weaker_decision_is_detected_as_a_regression() -> None:
    baseline = _baseline()
    weakened = json.loads(json.dumps(baseline["governance"]))
    weakened["planner_plan_list"]["decision"] = Decision.DENY.value

    assert governance_regressions(policy_parity_snapshot(), weakened) == (
        "planner_plan_list",
    )


def test_lower_security_tier_is_detected_as_a_regression() -> None:
    baseline = _baseline()
    weakened = json.loads(json.dumps(baseline["governance"]))
    weakened["planner_task_get"]["security_tier"] = 4

    assert governance_regressions(policy_parity_snapshot(), weakened) == (
        "planner_task_get",
    )


def test_dropped_capability_constraint_is_detected_as_a_regression() -> None:
    baseline = _baseline()
    weakened = json.loads(json.dumps(baseline["governance"]))
    weakened["planner_task_list"]["capability_keys"] = ["planner.nonexistent.capability"]

    assert governance_regressions(policy_parity_snapshot(), weakened) == (
        "planner_task_list",
    )


def test_missing_tool_is_detected_as_a_regression() -> None:
    snapshot = policy_parity_snapshot()
    del snapshot["planner_health"]

    assert governance_regressions(snapshot, _baseline()["governance"]) == (
        "planner_health",
    )


def test_decision_strength_order_is_monotonic() -> None:
    assert (
        DECISION_STRENGTH[Decision.ALLOW.value]
        < DECISION_STRENGTH[Decision.REQUIRE_APPROVAL.value]
        < DECISION_STRENGTH[Decision.DENY.value]
    )


def test_every_preserved_planner_tool_is_a_registered_read_with_mutations_disabled() -> None:
    registry = default_tool_registry()
    settings = Settings()

    assert settings.allow_mutations is False
    for tool in PLANNER_PUBLIC_TOOL_NAMES:
        definition = registry.get(tool)
        assert definition.mutation_class is MutationClass.READ
        assert definition.compatibility_requirement.value == "PRESERVE"


def test_unregistered_tool_fails_closed() -> None:
    with pytest.raises(KeyError):
        policy_projection("planner_not_a_registered_tool")


def test_projection_contains_no_credential_or_tenant_material() -> None:
    payload = json.dumps(policy_parity_snapshot()).lower()

    for forbidden in _FORBIDDEN_PROJECTION_KEYS:
        assert forbidden not in payload
    assert "/home/" not in payload
    assert "sqlite" not in payload


def test_compatibility_mutation_override_only_makes_every_planner_tool_stricter() -> None:
    settings = Settings()

    for tool in PLANNER_PUBLIC_TOOL_NAMES:
        strict = evaluate(tool, settings, mutation=True)
        assert strict.decision is Decision.DENY
        assert strict.reason == "MUTATIONS_DISABLED_IN_0_1_0"


def test_unregistered_planner_name_fails_closed_in_the_policy_engine() -> None:
    result = evaluate("planner_task_create", Settings())

    assert result.decision is Decision.DENY
    assert result.reason == "TOOL_NOT_REGISTERED"


def test_mismatched_explicit_scope_fails_closed() -> None:
    definition = default_tool_registry().get("planner_task_get")
    canonical = canonical_policy_scope(definition)
    widened = PolicyScope(
        application=canonical.application,
        surface=canonical.surface,
        account_scope=canonical.account_scope,
        container_scope="account",
        mailbox_scope=canonical.mailbox_scope,
        resource_scope=canonical.resource_scope,
    )

    result = evaluate("planner_task_get", Settings(), scope=widened)

    assert result.decision is Decision.DENY
    assert result.reason == "SCOPE_CONTAINER_MISMATCH"


def test_explicit_canonical_scope_is_accepted_and_marked_verified() -> None:
    definition = default_tool_registry().get("planner_plan_list")
    canonical = canonical_policy_scope(definition)

    result = evaluate("planner_plan_list", Settings(), scope=canonical)

    assert result.decision is Decision.ALLOW
    assert result.scope_reason == "SCOPE_VERIFIED"
    assert result.scope_derived is False


def test_baseline_scope_projection_matches_canonical_metadata_scope() -> None:
    registry = default_tool_registry()

    for tool, projection in _baseline()["governance"].items():
        canonical = canonical_policy_scope(registry.get(tool))
        assert projection["scope"] == {
            "application": canonical.application,
            "surface": canonical.surface,
            "account_scope": canonical.account_scope.value,
            "container_scope": canonical.container_scope,
            "mailbox_scope": canonical.mailbox_scope.value,
            "resource_scope": (
                canonical.resource_scope.value
                if canonical.resource_scope is not None
                else None
            ),
        }
        assert projection["scope_derived"] is True
        assert projection["scope_reason"] == "CANONICAL_SCOPE_DERIVED"


def test_capability_constrained_tools_declare_registered_planner_capabilities() -> None:
    registry = default_tool_registry()
    capabilities = default_capability_registry()
    declared = set(capabilities.capability_names("planner"))

    constrained = 0
    for tool in PLANNER_PUBLIC_TOOL_NAMES:
        keys = registry.get(tool).capability_keys
        if keys:
            constrained += 1
            assert set(keys).issubset(declared)
    assert constrained > 0


def test_mock_capability_state_never_reaches_read_supported_without_live_evidence() -> None:
    evidence = EffectiveCapabilityEvidence(
        authenticated=True,
        account_context_valid=True,
        ui_attested=True,
        runtime_healthy=True,
        policy_allowed=True,
        license_available=True,
        live_evidence=False,
    )

    projected = project_effective_capabilities(
        default_capability_registry(),
        application="planner",
        evidence=evidence,
    )

    assert projected
    for capability in projected:
        assert capability.state is EffectiveCapabilityState.UNVERIFIED_LIVE
        assert capability.supported is False
        assert "LIVE_EVIDENCE_ABSENT" in capability.reasons


def test_policy_denied_capability_state_is_blocked_fail_closed() -> None:
    evidence = EffectiveCapabilityEvidence(
        authenticated=True,
        account_context_valid=True,
        ui_attested=True,
        runtime_healthy=True,
        policy_allowed=False,
        license_available=True,
        live_evidence=True,
    )

    projected = project_effective_capabilities(
        default_capability_registry(),
        application="planner",
        evidence=evidence,
    )

    for capability in projected:
        assert capability.state is EffectiveCapabilityState.BLOCKED
        assert capability.reasons == ("POLICY_DENIED",)


def test_preserved_planner_output_schemas_forbid_graph_usage() -> None:
    schemas = planner_semantic_schemas()

    assert tuple(schemas) == PLANNER_PUBLIC_TOOL_NAMES
    for tool in PLANNER_PUBLIC_TOOL_NAMES:
        output = schemas[tool].output_schema
        assert "graph_api_used" in tuple(output["required"])
        assert output["properties"]["graph_api_used"] == {"const": False}
        assert output["properties"]["read_only"] == {"const": True}


def test_planner_policy_compatibility_exports_resolve_to_the_m365_engine() -> None:
    assert planner_policy.evaluate is evaluate
    assert planner_policy.Decision is Decision
    assert set(planner_policy.READ_TOOLS) == set(PLANNER_PUBLIC_TOOL_NAMES)
