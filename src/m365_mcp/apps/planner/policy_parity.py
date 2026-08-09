"""Planner policy parity projection for PLN-MIG-009.

The parity contract proves that no preserved Planner operation became *less
governed* after the generalized M365 platform extraction. It projects the
canonical, sanitized governance decision for every tool of the preserved
17-tool ``planner_*`` public surface and compares it against a frozen
governance baseline.

The projection contains policy classes only. It never contains tenant data,
mailbox addresses, session state, tokens or filesystem paths, and it never
converts a governance projection into a live-support claim.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from hashlib import sha256
from typing import Any

from m365_mcp.apps.planner.public_surface import PLANNER_PUBLIC_TOOL_NAMES
from m365_mcp.config import Settings
from m365_mcp.policy import Decision, MetadataPolicyEngine
from m365_mcp.policy_scope import PolicyScope
from m365_mcp.tool_registry import ToolRegistry, default_tool_registry

#: Governance strength order. A parity check fails if a tool moves to a weaker
#: decision than its frozen baseline.
DECISION_STRENGTH: Mapping[str, int] = {
    Decision.ALLOW.value: 0,
    Decision.REQUIRE_APPROVAL.value: 1,
    Decision.DENY.value: 2,
}


def _scope_projection(scope: PolicyScope | None) -> dict[str, Any] | None:
    if scope is None:
        return None
    return {
        "application": scope.application,
        "surface": scope.surface,
        "account_scope": scope.account_scope.value,
        "container_scope": scope.container_scope,
        "mailbox_scope": scope.mailbox_scope.value,
        "resource_scope": (
            scope.resource_scope.value if scope.resource_scope is not None else None
        ),
    }


def policy_projection(
    tool: str,
    settings: Settings | None = None,
    *,
    engine: MetadataPolicyEngine | None = None,
    registry: ToolRegistry | None = None,
) -> dict[str, Any]:
    """Return the sanitized governance projection of one semantic tool."""
    active_registry = registry or default_tool_registry()
    definition = active_registry.get(tool)
    result = (engine or MetadataPolicyEngine(active_registry)).evaluate(
        tool,
        settings or Settings(),
    )

    return {
        "tool": tool,
        "application": definition.application,
        "surface": definition.surface,
        "domain": definition.domain,
        "mutation_class": definition.mutation_class.value,
        "risk_class": definition.risk_class,
        "implementation_state": definition.implementation_state.value,
        "compatibility_requirement": definition.compatibility_requirement.value,
        "approval_requirement": definition.approval_requirement,
        "capability_keys": list(definition.capability_keys),
        "decision": result.decision.value,
        "reason": result.reason,
        "security_tier": int(result.security_tier) if result.security_tier is not None else None,
        "scope": _scope_projection(result.scope),
        "scope_reason": result.scope_reason,
        "scope_derived": result.scope_derived,
    }


def policy_parity_snapshot(
    tools: tuple[str, ...] = PLANNER_PUBLIC_TOOL_NAMES,
    settings: Settings | None = None,
    *,
    registry: ToolRegistry | None = None,
) -> dict[str, Any]:
    """Project governance for the preserved Planner public surface, in order."""
    active_registry = registry or default_tool_registry()
    engine = MetadataPolicyEngine(active_registry)
    active_settings = settings or Settings()
    return {
        tool: policy_projection(
            tool,
            active_settings,
            engine=engine,
            registry=active_registry,
        )
        for tool in tools
    }


def policy_parity_digest(snapshot: Mapping[str, Any]) -> str:
    """Return a stable digest for a governance parity snapshot."""
    payload = json.dumps(snapshot, sort_keys=True, separators=(",", ":"))
    return f"sha256:{sha256(payload.encode('utf-8')).hexdigest()}"


def governance_regressions(
    snapshot: Mapping[str, Mapping[str, Any]],
    baseline: Mapping[str, Mapping[str, Any]],
) -> tuple[str, ...]:
    """Return tools whose governance became weaker than the frozen baseline.

    Weaker means a lower decision strength, a lower security tier, a dropped
    approval requirement or a lost capability constraint.
    """
    regressions: list[str] = []
    for tool, expected in baseline.items():
        observed = snapshot.get(tool)
        if observed is None:
            regressions.append(tool)
            continue
        if (
            DECISION_STRENGTH[str(observed["decision"])]
            < DECISION_STRENGTH[str(expected["decision"])]
        ):
            regressions.append(tool)
            continue
        if int(observed["security_tier"]) < int(expected["security_tier"]):
            regressions.append(tool)
            continue
        if (
            expected["approval_requirement"] != "none"
            and observed["approval_requirement"] == "none"
        ):
            regressions.append(tool)
            continue
        if not set(expected["capability_keys"]).issubset(set(observed["capability_keys"])):
            regressions.append(tool)
    return tuple(regressions)


__all__ = [
    "DECISION_STRENGTH",
    "governance_regressions",
    "policy_parity_digest",
    "policy_parity_snapshot",
    "policy_projection",
]
