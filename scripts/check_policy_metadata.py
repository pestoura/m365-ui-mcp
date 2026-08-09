#!/usr/bin/env python3
"""REL-008 — Policy metadata completeness gate.

Fails closed when any registered semantic tool lacks the metadata the
metadata-driven policy engine needs to reach a deterministic decision, or
when policy evaluation cannot classify a registered tool.

The gate makes no live-support claim and performs no network or tenant access.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from m365_mcp.capability_registry import default_capability_registry  # noqa: E402
from m365_mcp.config import Settings  # noqa: E402
from m365_mcp.policy import Decision, MetadataPolicyEngine  # noqa: E402
from m365_mcp.security_tiers import SecurityTier  # noqa: E402
from m365_mcp.tool_registry import (  # noqa: E402
    CompatibilityRequirement,
    ImplementationState,
    MutationClass,
    default_tool_registry,
)

REQUIRED_TEXT_FIELDS = (
    "version",
    "surface",
    "domain",
    "risk_class",
    "read_back_strategy",
    "idempotency_semantics",
    "approval_requirement",
)

APPROVAL_VALUES = {"none", "required", "dual_control"}


def main() -> None:
    """Run the policy metadata completeness gate."""
    registry = default_tool_registry()
    capabilities = default_capability_registry()
    engine = MetadataPolicyEngine(registry, capabilities)
    settings = Settings(mode="mock")

    violations: list[dict[str, str]] = []

    def fail(tool: str, rule: str, detail: str = "") -> None:
        violations.append({"tool": tool, "rule": rule, "detail": detail})

    for name in registry.names():
        definition = registry.get(name)

        for field in REQUIRED_TEXT_FIELDS:
            value = getattr(definition, field)
            if not isinstance(value, str) or not value.strip():
                fail(name, "missing_metadata_field", field)

        if definition.approval_requirement not in APPROVAL_VALUES:
            fail(name, "unknown_approval_requirement", definition.approval_requirement)
        if not isinstance(definition.mutation_class, MutationClass):
            fail(name, "invalid_mutation_class", str(definition.mutation_class))
        if not isinstance(definition.implementation_state, ImplementationState):
            fail(name, "invalid_implementation_state", str(definition.implementation_state))
        if not isinstance(definition.compatibility_requirement, CompatibilityRequirement):
            fail(name, "invalid_compatibility_requirement", "")

        for key in definition.capability_keys:
            if not capabilities.has_capability(definition.application, key):
                fail(name, "capability_key_not_registered", key)

        result = engine.evaluate(name, settings)
        if result.decision not in set(Decision):
            fail(name, "policy_decision_not_closed", str(result.decision))
        if result.reason in {"TOOL_NOT_REGISTERED", "SCOPE_METADATA_INVALID"}:
            fail(name, "policy_cannot_classify_registered_tool", result.reason)
        if result.security_tier is None or result.security_tier not in set(SecurityTier):
            fail(name, "security_tier_not_projected", str(result.security_tier))
        if result.scope is None:
            fail(name, "policy_scope_not_bounded", "")
        if result.decision is Decision.ALLOW and definition.mutation_class is not (
            MutationClass.READ
        ):
            fail(name, "mutation_allowed_without_approval", definition.mutation_class.value)

    report = {
        "control": "policy-metadata-completeness",
        "requirement": "REL-008",
        "tools_checked": len(registry.names()),
        "violations": violations,
        "status": "PASS" if not violations else "FAIL",
    }
    out = ROOT / "artifacts"
    out.mkdir(exist_ok=True)
    (out / "policy-metadata-completeness.json").write_text(
        json.dumps(report, indent=2, sort_keys=True), encoding="utf-8"
    )
    print(json.dumps(report, indent=2, sort_keys=True))
    sys.exit(0 if not violations else 1)


if __name__ == "__main__":
    main()
