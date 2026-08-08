# CORE-008 — Canonical Tool Registry

## Decision

`m365_mcp.tool_registry` is the canonical governance metadata model for semantic MCP tools.

CORE-008 deliberately does **not** replace the existing explicit FastMCP wrappers. That projection remains unchanged until CORE-009 proves metadata-driven registration can preserve the exact public Planner schemas and names.

## Required metadata

Each `ToolDefinition` carries:

```text
name
version
application
surface
domain
input_schema
output_schema
mutation_class
risk_class
implementation_state
capability_keys
ui_contract_dependencies
read_back_strategy
idempotency_semantics
approval_requirement
compatibility_requirement
```

The implementation-state vocabulary is exactly:

```text
IMPLEMENTED_LIVE
IMPLEMENTED_MOCK_ONLY
IMPLEMENTED_NOT_ATTESTED
SPECIFIED_ONLY
PLANNED
DEPRECATED
BLOCKED
```

The compatibility vocabulary is:

```text
PRESERVE
VERSION
DEPRECATE_LATER
INTERNAL_ONLY
```

## Current 0.1.0 inventory

- 17 definitions;
- all application = `planner`;
- all public names remain `planner_*`;
- all mutation class = `READ`;
- all compatibility = `PRESERVE`;
- no current definition is promoted to `IMPLEMENTED_LIVE` without live attestation evidence;
- no Outlook semantic tool exists yet.

The registry is validated against the current Python `TOOL_NAMES`, ToolManifest and ExtendedToolManifest so documentation/contract declarations cannot silently diverge from the public surface.

## Security and architecture

- duplicate names fail closed;
- application/name prefix mismatches fail closed;
- input and output schemas must be object schemas;
- risk, read-back, idempotency and approval metadata are mandatory;
- UIContract dependencies explicitly retain the current global/decomposed-selector debt rather than pretending target fragmentation already exists;
- no callable, browser primitive, credential or session material is stored in registry metadata.

CORE-009 will consume this registry for semantic projection while retaining explicit closed handlers. It must not introduce `eval`, shell, JavaScript, selectors, XPath or a generic browser executor.
