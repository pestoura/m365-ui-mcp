# Transition Blueprint Reconciliation

Reconciled against Planner baseline `planner-pre-m365-0.1.0` (`232c72632ab5c93d0bee70ac588af08422cbc42d`).

## Reconciliation vocabulary

`STILL_REQUIRED`, `ALREADY_IMPLEMENTED`, `SUPERSEDED`, `REQUIRES_REDESIGN`.

| Blueprint proposal | Decision | Baseline finding |
|---|---|---|
| Preserve `planner_*` public tools | ALREADY_IMPLEMENTED | 17 public read-only names form the compatibility baseline; all are marked PRESERVE. |
| Explicit contract/schema versioning | ALREADY_IMPLEMENTED | P-004 established canonical 0.1.0 version truth and versioned schemas. |
| Generic M365 product/package identity | STILL_REQUIRED | Packages/config/entry points remain Planner-specific. |
| Canonical Tool Registry | STILL_REQUIRED | No runtime metadata-driven registry exists. |
| Dynamic/profiled tool projection | STILL_REQUIRED | Static registrations remain. |
| Scoped Capability Registry | STILL_REQUIRED | Current capability model is Planner/global, not app/surface/account/container scoped. |
| Fragmented UIContract | STILL_REQUIRED | Current contract is one global unattested Planner document. |
| Per-fragment attestation/drift blast-radius containment | STILL_REQUIRED | Current live gate is global. |
| Browser lifespan ownership | STILL_REQUIRED | PersistentBrowser exists but FastAPI lifespan does not own/prove it. |
| Strong readiness proving Chromium | STILL_REQUIRED | Current health/readiness can succeed without real Chromium operation. |
| Session/Capability Broker | STILL_REQUIRED | Browser profile is the right boundary, but broker abstraction does not exist. |
| Private worker ingress | ALREADY_IMPLEMENTED | Worker port is not publicly published. |
| Controlled Microsoft egress | REQUIRES_REDESIGN | Current Docker `internal: true` network blocks required live egress. |
| Closed typed worker operation protocol | STILL_REQUIRED | WorkerClient uses ad-hoc HTTP endpoint methods. |
| No generic browser executor | ALREADY_IMPLEMENTED | Preserve as a non-regression invariant. |
| Metadata-driven policy | STILL_REQUIRED | Current read policy uses a hardcoded tool-name set. |
| Approvals/locks/idempotency/sagas/checkpoints | REQUIRES_REDESIGN | Persistence/skeletons exist, but must be generalized and wired into the M365 execution plane. |
| Generalized state identity | STILL_REQUIRED | Current resource identity does not carry account/application/container/resource tuple. |
| Result shaping | STILL_REQUIRED | No generic projection/pagination operators yet. |
| Full execution provenance | STILL_REQUIRED | Version fields exist, but no target digest/provenance envelope. |
| Token/context economics metrics | STILL_REQUIRED | Current metrics are operational skeleton only. |
| DIRECT deterministic execution | ALREADY_IMPLEMENTED | Current semantic reads already execute without an intermediate Hermes/LLM hop; retain and expand. |
| BATCH | STILL_REQUIRED | Not implemented. |
| DAG | STILL_REQUIRED | Not implemented. |
| RUNBOOK | STILL_REQUIRED | Not implemented. |
| Controlled HYBRID/agentic fallback | STILL_REQUIRED | Not implemented and must remain bounded. |
| Mandatory mutation read-back | STILL_REQUIRED | Baseline has zero writes; target rule remains mandatory before writes are promoted. |
| Outlook adapter | STILL_REQUIRED | No Outlook implementation exists in Planner baseline. |
| Planner parity gate before Outlook live | STILL_REQUIRED | Becomes the principal migration invariant. |
| Session secret export | SUPERSEDED | The blueprint already rejects token/cookie export; no credential-broker copy is required. Use Session/Capability Broker instead. |

## Hermes MCP Bridge V2 reconciliation

The current `pestoura/hermes-mcp-bridge/docs/v2/` still supports the selected architecture:

```text
DETERMINISTIC WORK -> CODE
KNOWN WORKFLOW    -> RUNBOOK
REASONING         -> LLM
```

and the execution preference:

```text
DIRECT > BATCH > DAG/RUNBOOK > AGENTIC
```

The M365 adaptation remains valid. The browser session is the authentication boundary; Hermes-style token brokering is not copied literally. Tool Registry, capability projection, plan digests, per-node policy, replay protection, sagas/checkpoints, result shaping and provenance remain design inputs, not a reason to runtime-couple the two products.
