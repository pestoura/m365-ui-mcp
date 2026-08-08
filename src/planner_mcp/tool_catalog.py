"""The declarative 0.1.0 read-only tool catalogue.

Semantic tools only: no generic click/type/navigate/eval tool may ever be added here.
Every entry is READ class in 0.1.0. The auth tools orchestrate an interactive human login;
they never submit credentials and never approve MFA (ADR-004).
"""

from __future__ import annotations

from planner_mcp.contracts import ExtendedToolManifest
from planner_mcp.enums import (
    ApprovalRequirement,
    CapabilityState,
    IdempotencyClass,
    MutationClass,
    TrustLevel,
)

#: Substrings that must never appear in a tool name — semantic tools only.
FORBIDDEN_NAME_FRAGMENTS: frozenset[str] = frozenset(
    {"click", "type", "navigate", "goto", "eval", "script", "keyboard", "mouse", "screenshot"}
)


def _tool(
    name: str,
    title: str,
    description: str,
    *,
    trust: TrustLevel = TrustLevel.TENANT_READ,
    policy_rule_id: str = "POL-READ-DEFAULT",
    read_back: str = "n/a",
    ui_refs: tuple[str, ...] = (),
) -> ExtendedToolManifest:
    return ExtendedToolManifest(
        name=name,
        title=title,
        description=description,
        trust_level=trust,
        mutation_class=MutationClass.READ,
        reversible=True,
        idempotency_class=IdempotencyClass.PURE_READ,
        approval_requirement=ApprovalRequirement.NONE,
        attestation_status=CapabilityState.UNVERIFIED_LIVE,
        policy_rule_id=policy_rule_id,
        read_back_strategy=read_back,
        drift_behavior="FAIL_CLOSED",
        ui_contract_refs=ui_refs,
    )


CATALOG_0_1_0: tuple[ExtendedToolManifest, ...] = (
    _tool(
        "planner_health",
        "Health",
        "Liveness of the control plane. Never touches the browser worker or the tenant.",
        trust=TrustLevel.INTROSPECTION,
        policy_rule_id="POL-INTROSPECT",
    ),
    _tool(
        "planner_readiness",
        "Readiness",
        "Aggregate readiness: worker reachable, UIContract loaded, auth state, policy loaded.",
        trust=TrustLevel.INTROSPECTION,
        policy_rule_id="POL-INTROSPECT",
    ),
    _tool(
        "planner_capabilities",
        "Capability manifest",
        "Return the capability matrix with evidence state. Graph is never a functional gate.",
        trust=TrustLevel.INTROSPECTION,
        policy_rule_id="POL-INTROSPECT",
    ),
    _tool(
        "planner_agent_card",
        "Agent card",
        "Identity, versions, boundaries and fail-closed conditions of this server.",
        trust=TrustLevel.INTROSPECTION,
        policy_rule_id="POL-INTROSPECT",
    ),
    _tool(
        "planner_ui_contract_status",
        "UIContract status",
        "Loaded UIContract version, attestation coverage and current drift findings.",
        trust=TrustLevel.INTROSPECTION,
        policy_rule_id="POL-INTROSPECT",
    ),
    _tool(
        "planner_auth_status",
        "Auth status",
        "Current authentication state; never returns cookies, tokens or credentials.",
        trust=TrustLevel.INTROSPECTION,
        policy_rule_id="POL-AUTH-READ",
    ),
    _tool(
        "planner_auth_start",
        "Start interactive authentication",
        "Open the interactive sign-in surface in the persistent profile for a human to "
        "complete. Submits nothing; emits a sanitized MFA event if number matching appears.",
        trust=TrustLevel.PRIVILEGED,
        policy_rule_id="POL-AUTH-INTERACTIVE",
        read_back="auth_state re-read after the human completes the flow",
    ),
    _tool(
        "planner_auth_resume",
        "Resume interactive authentication",
        "Re-evaluate an in-progress interactive sign-in and advance the auth state machine.",
        trust=TrustLevel.PRIVILEGED,
        policy_rule_id="POL-AUTH-INTERACTIVE",
        read_back="auth_state re-read from the live session",
    ),
    _tool(
        "planner_auth_session_info",
        "Session info",
        "Non-sensitive session metadata: state, age, expiry estimate, profile identity hash.",
        trust=TrustLevel.INTROSPECTION,
        policy_rule_id="POL-AUTH-READ",
    ),
    _tool(
        "planner_plan_list",
        "List plans",
        "Enumerate plans visible to the signed-in account in the tenant UI.",
        read_back="typed list re-read on retry",
    ),
    _tool(
        "planner_plan_get",
        "Get plan",
        "Typed read of one plan's attributes and structure.",
        read_back="entity re-read by stable external_id",
    ),
    _tool(
        "planner_task_list",
        "List tasks",
        "Enumerate the tasks of a plan or bucket.",
        read_back="typed list re-read on retry",
    ),
    _tool(
        "planner_task_get",
        "Get task",
        "Typed read of one task including its scheduling fields.",
        read_back="entity re-read by stable external_id",
    ),
    _tool(
        "planner_project_snapshot",
        "Project snapshot",
        "Consistent point-in-time read model of a project: plan, buckets, tasks, structure.",
        read_back="snapshot hash compared across two consecutive reads",
    ),
    _tool(
        "planner_account_context",
        "Account context",
        "Sanitized signed-in identity context; no mailbox, no tokens, no personal data dump.",
        trust=TrustLevel.INTROSPECTION,
        policy_rule_id="POL-AUTH-READ",
    ),
    _tool(
        "planner_license_capabilities",
        "License capabilities",
        "Premium surfaces observed for the signed-in account, read from the UI only.",
    ),
    _tool(
        "planner_smoke_test",
        "Smoke test",
        "Read-only end-to-end probe: worker, session, UIContract and one deterministic read.",
        policy_rule_id="POL-SMOKE",
        read_back="probe result compared against the expected deterministic shape",
    ),
)

CATALOG_BY_NAME: dict[str, ExtendedToolManifest] = {t.name: t for t in CATALOG_0_1_0}

__all__ = ["CATALOG_0_1_0", "CATALOG_BY_NAME", "FORBIDDEN_NAME_FRAGMENTS"]
