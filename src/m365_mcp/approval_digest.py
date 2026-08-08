"""Canonical immutable approval-plan digest for CORE-035.

The digest binds only reviewed semantic execution metadata. It deliberately
contains no Microsoft tenant content, raw resource identifier, mailbox address,
browser profile path, cookie, token or storage state.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

from m365_mcp.plan_policy import PolicyPlan
from m365_mcp.policy import MetadataPolicyEngine
from m365_mcp.policy_scope import PolicyScope, assess_policy_scope
from m365_mcp.security_tiers import classify_security_tier
from m365_mcp.tool_registry import MutationClass

_DIGEST_SCHEMA_VERSION = "approval-plan-v1"
_DIGEST_ALGORITHM = "sha256"


@dataclass(frozen=True)
class ApprovalPlanDigest:
    """Opaque digest and bounded metadata for one exact approval plan."""

    schema_version: str
    algorithm: str
    value: str
    node_count: int

    def __post_init__(self) -> None:
        if self.schema_version != _DIGEST_SCHEMA_VERSION:
            raise ValueError("unsupported approval plan digest schema")
        if self.algorithm != _DIGEST_ALGORITHM:
            raise ValueError("unsupported approval plan digest algorithm")
        if len(self.value) != 64 or any(char not in "0123456789abcdef" for char in self.value):
            raise ValueError("approval plan digest must be lowercase SHA-256 hex")
        if self.node_count < 2:
            raise ValueError("approval plan digest requires a multi-node plan")


def _scope_payload(scope: PolicyScope) -> dict[str, str | None]:
    return {
        "application": scope.application,
        "surface": scope.surface,
        "account_scope": scope.account_scope.value,
        "container_scope": scope.container_scope,
        "mailbox_scope": scope.mailbox_scope.value,
        "resource_scope": scope.resource_scope.value if scope.resource_scope else None,
    }


def build_approval_plan_digest(
    plan: PolicyPlan,
    *,
    engine: MetadataPolicyEngine | None = None,
) -> ApprovalPlanDigest:
    """Digest the exact policy-relevant shape of a multi-node mutating plan.

    This function does not grant approval. CORE-036 owns approval persistence
    and atomic consumption. Digest creation fails closed for unknown tools,
    invalid scopes, read-only plans and single-node plans.
    """
    if len(plan.nodes) < 2:
        raise ValueError("approval plan digest requires a multi-node plan")

    policy_engine = engine or MetadataPolicyEngine()
    node_payloads: list[dict[str, object]] = []
    has_mutation = False

    for node in plan.nodes:
        try:
            definition = policy_engine.registry.get(node.tool)
        except KeyError as exc:
            raise ValueError(f"approval plan contains unregistered tool: {node.tool}") from exc

        assessment = assess_policy_scope(
            definition,
            node.scope,
            policy_engine.capability_registry,
        )
        if not assessment.allowed:
            raise ValueError(f"approval plan contains invalid node scope: {node.node_id}")

        metadata_mutation = definition.mutation_class is not MutationClass.READ
        effective_mutation = metadata_mutation or node.mutation
        has_mutation = has_mutation or effective_mutation
        tier = classify_security_tier(definition).tier

        node_payloads.append(
            {
                "node_id": node.node_id,
                "tool": definition.name,
                "tool_version": definition.version,
                "mutation_class": definition.mutation_class.value,
                "security_tier": tier.name,
                "effective_mutation": effective_mutation,
                "scope": _scope_payload(assessment.effective_scope),
                "depends_on": sorted(node.depends_on),
            }
        )

    if not has_mutation:
        raise ValueError("approval plan digest requires at least one mutating node")

    payload = {
        "schema_version": _DIGEST_SCHEMA_VERSION,
        "plan_kind": plan.kind.value,
        "nodes": node_payloads,
    }
    canonical = json.dumps(
        payload,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    value = hashlib.sha256(canonical).hexdigest()
    return ApprovalPlanDigest(
        schema_version=_DIGEST_SCHEMA_VERSION,
        algorithm=_DIGEST_ALGORITHM,
        value=value,
        node_count=len(plan.nodes),
    )


__all__ = ["ApprovalPlanDigest", "build_approval_plan_digest"]
