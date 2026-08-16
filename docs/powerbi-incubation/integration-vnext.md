# Power BI UI MCP — M365 VNext Integration

## Objective

Power BI is incubated now so the design is not lost, but implementation/integration starts only after the current Planner + Outlook M365 program reaches its accepted baseline.

## Target sequence

```text
m365-ui-mcp current program
  |
  +-- Planner migration/parity
  +-- Outlook implementation
  +-- shared core / UI contract / auth / policy
  |
  v
M365 acceptance baseline GREEN
  |
  v
freeze + tag baseline
  |
  v
Power BI integration version
  |
  +-- register `powerbi` application
  +-- add dedicated worker/container
  +-- reuse generic control-plane contracts
  +-- reuse auth/MFA notification contracts
  +-- add Power BI-specific UI state/capabilities
  +-- add TMDL/DAX/M fast paths
  +-- add report/canvas engine
  |
  v
M365 Planner + Outlook + Power BI
```

## Reuse versus isolation

### Reuse from M365 core

- MCP control-plane infrastructure;
- application/tool registry;
- policy engine;
- capability registry/projector;
- UIContract storage/attestation concepts;
- audit/redaction/evidence manifest format;
- health/readiness conventions;
- generic worker protocol;
- authentication state abstractions;
- Hermes notification integration contract;
- retry/error taxonomy;
- metrics/tracing conventions.

### Power BI-specific implementation

- dedicated Chromium profile/runtime;
- Power BI state machine and UI contract fragments;
- report editor primitives;
- canvas/visual geometry engine;
- formatting pane semantics;
- filters/slicers/interactions/bookmarks;
- semantic model editor semantics;
- TMDL/DAX/M fast-path adapters;
- Power BI macro/spec engine;
- Power BI acceptance fixtures.

### Must remain isolated

- cookies/session state;
- browser profile;
- screenshots/evidence directories;
- raw authentication artifacts;
- application-specific UI drift state;
- destructive/mutation locks.

## Tool profiles

Future shared MCP should support bounded projections such as:

```text
full
planner
outlook
powerbi
read-only
```

The Power BI module should expose a compact public semantic surface. Internal primitives do not automatically become public tools.

## Cross-application workflows

Power BI integration creates useful cross-application workflows, but they must be orchestrated above the individual application workers.

Example:

```text
Planner worker
   -> inspect project activities/sprints/dependencies
   -> normalized cross-app data contract
   -> Power BI worker
   -> create/update management visuals and measures
```

The target is not to share browser sessions or scrape one application's internal state from another.

Potential workflows:

```text
XAPP: Planner -> Power BI sprint dashboard
XAPP: Planner -> Power BI blocked/dependency KPIs
XAPP: Planner -> Power BI workload/owner distribution
XAPP: Outlook calendar/categories -> Power BI management reporting (only if justified)
```

## Version boundary

Do not introduce Power BI into the current M365 release merely because the blueprint exists.

Power BI starts at a deliberate new version boundary after:

1. current M365 acceptance is green;
2. baseline/tag is captured;
3. Power BI blueprint is reconciled against final core;
4. live capability discovery is authorized;
5. dedicated Power BI worker isolation is in place.

## Migration from standalone incubation repository

If `pestoura/powerbi-ui-mcp` is used during incubation:

- treat shared-core copies as temporary scaffolding;
- record every borrowed M365 contract and upstream source;
- avoid independent incompatible auth/policy/tool-registry designs;
- merge/reconcile through explicit ADRs;
- preserve `PBI-*` backlog identifiers during integration;
- archive or mark the standalone repo read-only after canonical integration if it no longer has an independent product purpose.
