# CORE-007 — Application Registry decision

## Decision

The M365 core uses a closed, explicit, schema-like in-code Application Registry. Application adapters cannot self-register through package entry points, filesystem discovery, import side effects or arbitrary plugin loading.

The stable application identifiers introduced by CORE-007 are:

```text
planner
outlook
```

## Current execution state

| Application | Registry state | Registrar | Runtime meaning |
|---|---|---|---|
| `planner` | `ENABLED` | `planner_mcp.registration.register_planner_tools` | Projects the existing 17 preserved `planner_*` tools. |
| `outlook` | `RESERVED` | none | Known to the core, but cannot expose tools or execute UI operations before Planner parity and the ordered Outlook phase. |

The roadmap phrase "register enabled modules: planner, outlook" is reconciled with the stronger sequencing invariant that Outlook implementation must not start before the core and Planner parity are stable. CORE-007 therefore registers both application identities, but only marks an application `ENABLED` when a validated semantic registrar exists and the phase gate permits execution.

## Security properties

- duplicate application keys fail closed;
- `ENABLED` without a registrar is invalid;
- `RESERVED` with a registrar is invalid;
- registration order is deterministic;
- no automatic plugin discovery;
- no raw browser/action surface;
- no session-secret/cookie/token/storage-state export;
- no Outlook tool or live UI execution is introduced by CORE-007.

## Compatibility

The FastMCP projection remains exactly the current Planner 0.1.0 public surface. `m365_mcp.server` now obtains its registrar from the Application Registry; the 17 `planner_*` signatures and behavior remain unchanged.

CORE-008 will add the canonical Tool Registry. CORE-009 will later project tools from validated metadata without introducing a generic executor.
