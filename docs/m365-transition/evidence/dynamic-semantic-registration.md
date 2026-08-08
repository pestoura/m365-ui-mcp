# CORE-009 — Dynamic semantic MCP registration

## Decision

Public MCP exposure is now selected and ordered from validated Tool Registry metadata, but execution handlers remain explicit typed Python functions.

This is deliberately **not** a generic executor.

```text
Tool Registry definition
        ↓ exact name
closed typed handler binding
        ↓
FastMCP registration
```

For the Planner compatibility surface, `planner_mcp.registration` builds a closed mapping containing the 17 existing explicit handlers. Registration then iterates the Planner definitions from `default_tool_registry()` and exposes only exact definition/binding matches.

## Fail-closed invariants

Before any handler is registered:

- every registry definition must have exactly one binding;
- every binding must have exactly one registry definition;
- missing and unexpected bindings abort registration;
- public handler names remain the registry names;
- handler Python signatures remain explicit and typed;
- no `*args` / `**kwargs` registration shim is allowed.

## Security boundary

CORE-009 does not add or permit:

```text
browser_exec
click/selector primitives
javascript
xpath
eval/exec
shell/subprocess arbitrary execution
```

The registry contains governance metadata, not callables. Each application adapter supplies a closed semantic binding set. This keeps deterministic work in code and prevents registry metadata from becoming an arbitrary execution channel.

## Compatibility

The Planner 0.1.0 exposure remains exactly 17 `planner_*` tools with the same names and typed signatures. Existing ToolManifest/ExtendedToolManifest equivalence is retained by CORE-008 tests and existing server/release tests.

Outlook remains `RESERVED` in the Application Registry and has no tool definitions or bindings at this stage.

CORE-010 adds bounded exposure profiles over validated definitions; projection may hide tools but must never weaken policy.
