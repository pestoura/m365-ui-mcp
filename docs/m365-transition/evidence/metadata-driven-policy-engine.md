# CORE-031 — Metadata-driven policy engine

Status: **IMPLEMENTED_AWAITING_GATES**

## Objective

Remove hard-coded semantic tool-name allowlists from policy decisions and make the canonical `ToolRegistry` the policy source of truth.

## Implementation

`m365_mcp.policy.MetadataPolicyEngine` resolves the exact registered `ToolDefinition` and derives policy context from metadata including application, mutation class and capability keys.

Decision rules at this stage are deliberately narrow:

- unregistered tool -> `DENY / TOOL_NOT_REGISTERED`;
- registered mutation while mutations are disabled -> `DENY / MUTATIONS_DISABLED_IN_0_1_0`;
- registered mutation or metadata-declared approval -> `REQUIRE_APPROVAL` when mutation execution is enabled by a future runtime policy;
- registered read -> `ALLOW / REGISTERED_READ_TOOL`.

The historical `mutation=True` argument remains only as a compatibility safety override: it may make a decision stricter, never less governed.

## Compatibility

`planner_mcp.policy` is now a compatibility export of the canonical M365 engine. `READ_TOOLS` remains available but is generated from `default_tool_registry()` entries whose `mutation_class` is `READ`; it is no longer a manually maintained name set.

All 17 current Planner public tools therefore retain their existing read-policy behavior without duplicating their names in policy code.

## Boundaries

CORE-031 does not define security tiers or resource scope policy. Those remain CORE-032 and CORE-033 respectively. It also does not activate Outlook or public mutations.

## Acceptance coverage

Tests prove that:

- the compatibility read set is derived from registry metadata and contains all 17 Planner tools;
- an arbitrary registered read tool is allowed without a name allowlist;
- an arbitrary registered mutation is denied from mutation metadata when mutations are disabled;
- mutation metadata maps to approval when tested against an explicitly permissive policy context;
- unknown tools remain denied even in a permissive context;
- the compatibility mutation override can only tighten policy.
