# Planner Final Implementation Inventory

Baseline: `planner-pre-m365-0.1.0`  
Commit: `232c72632ab5c93d0bee70ac588af08422cbc42d`  
Product/contract/schema/UIContract/tool-catalog version: `0.1.0`

## Classification rule

Only code whose real execution path exists is treated as implemented. Documentation, manifests, package skeletons and capability rows do not promote a capability to implemented. No Planner capability is classified `IMPLEMENTED_LIVE` because the baseline UIContract is `UNVERIFIED_LIVE` and the live browser-worker Planner handlers are placeholders.

## Control plane

| Subsystem | State | Evidence/decision |
|---|---|---|
| FastMCP server + streamable HTTP | IMPLEMENTED_NOT_ATTESTED | Real FastMCP server registers the 17 current public tools. Runtime is covered by isolated/mock CI, not a live tenant campaign. |
| Typed configuration | IMPLEMENTED_NOT_ATTESTED | Pydantic settings, `PLANNER_*` namespace, live-mode validation and credential-shaped env rejection exist. |
| Product/contract/schema versioning | IMPLEMENTED_NOT_ATTESTED | P-004 merged; `src/planner_mcp/version.py` is canonical 0.1.0 and CI validates schemas/contracts. |
| AgentCard / ToolManifest / ExtendedToolManifest / CapabilityManifest | IMPLEMENTED_NOT_ATTESTED | Versioned contracts exist and validate; they describe baseline behavior but do not attest tenant capability. |
| Canonical Tool Registry | PLANNED | No metadata-driven runtime registry exists. Current policy and registration are static. `CORE-008` remains required. |
| Policy engine | IMPLEMENTED_NOT_ATTESTED | Fail-closed policy exists, but read allowlisting is hardcoded by public tool name. Metadata-driven redesign remains required (`CORE-031`). |
| Approvals | SPECIFIED_ONLY | State/schema scaffolding exists; no live mutation execution path consumes approvals. |
| Locks | SPECIFIED_ONLY | Persistence/types exist; no complete worker execution-plane integration. |
| Idempotency | SPECIFIED_ONLY | State table/scaffolding exists; no mutation/read-back execution path. |
| Sagas | SPECIFIED_ONLY | Persistence/package scaffolding only. |
| Checkpoints | SPECIFIED_ONLY | Persistence/package scaffolding only. |
| Reconciliation | SPECIFIED_ONLY | Models/scaffolding exist; no live Planner reconciliation loop. |
| State store / migrations | IMPLEMENTED_NOT_ATTESTED | SQLite v1, WAL/FULL/FK/busy timeout and tables exist. Identity model is not M365-scoped and requires `CORE-037`. |
| Health | IMPLEMENTED_NOT_ATTESTED | Process/worker checks exist. |
| Readiness | IMPLEMENTED_NOT_ATTESTED | Current readiness does not prove Chromium has started and is usable; semantics must be strengthened by `CORE-022`. |
| Error taxonomy | IMPLEMENTED_NOT_ATTESTED | Stable sanitized error codes include UI drift, policy and Conditional Access blockers. |
| Result shaping / pagination | PLANNED | No generic fields/select/count/top_n/cursor execution layer. `CORE-044` remains required. |
| Retry / circuit breaker | PLANNED | No generalized governed retry/circuit-breaker layer in Planner baseline. |
| Logging / redaction | IMPLEMENTED_NOT_ATTESTED | Structured redaction code and CI tests exist. |
| Metrics | IMPLEMENTED_NOT_ATTESTED | Low-cardinality Prometheus skeleton exists; token/context economics metrics do not. |
| Provenance | SPECIFIED_ONLY | Version fields exist in responses, but the target execution provenance envelope/digests are not implemented. |
| WorkerClient | IMPLEMENTED_NOT_ATTESTED | Real HTTP client exists, but uses ad-hoc endpoint methods rather than a typed closed worker protocol. `CORE-028/029` remain required. |

## Browser worker

| Subsystem | State | Evidence/decision |
|---|---|---|
| FastAPI worker | IMPLEMENTED_NOT_ATTESTED | Real app exists and is exercised in mock CI. |
| Playwright lifecycle abstraction | IMPLEMENTED_NOT_ATTESTED | `async_playwright` + persistent Chromium context code exists. |
| FastAPI lifespan owns Chromium | SPECIFIED_ONLY | Browser start/stop is not owned/proved by application lifespan. `CORE-021` required. |
| Persistent professional profile abstraction | IMPLEMENTED_NOT_ATTESTED | Dedicated profile directory is implemented; no live tenant attestation. |
| Auth state machine | IMPLEMENTED_MOCK_ONLY | Guarded state model exists, but worker live auth handlers do not implement the real end-to-end flow. |
| MFA handling | IMPLEMENTED_MOCK_ONLY | Number matching is modeled/detected; no automated approval and no live campaign evidence. Human interaction remains mandatory. |
| Conditional Access handling | IMPLEMENTED_NOT_ATTESTED | Fail-closed marker/error handling exists; no bypass. |
| Account-context validation | IMPLEMENTED_MOCK_ONLY | Mock path exists; live path does not establish real account/tenant context. |
| Licence/capability discovery | IMPLEMENTED_MOCK_ONLY | Mock evidence + capability model exist; no real tenant discovery. |
| Navigation | SPECIFIED_ONLY | No mature semantic live navigation implementation. |
| Selectors/locators | BLOCKED | All 10 UIContract selector values are null and `UNVERIFIED_LIVE`; fabrication is forbidden. |
| UIContract loader | IMPLEMENTED_NOT_ATTESTED | Global contract is loaded/validated. |
| UI attestation | BLOCKED | No live attestation evidence exists. |
| UI drift | IMPLEMENTED_NOT_ATTESTED | Global fail-closed drift/version behavior exists; fragment-level degradation does not. |
| Read-back | SPECIFIED_ONLY | Required by target architecture; baseline has no mutation paths and no generalized read-back primitive. |
| Queue/concurrency | PLANNED | No profile-level bounded serialized executor. `CORE-026` required. |
| Locks integration | SPECIFIED_ONLY | Not wired as an end-to-end worker execution primitive. |
| Typed worker operations | PLANNED | Current control-plane client calls ad-hoc REST endpoints. No generic raw browser endpoint exists, which must remain invariant. |
| Worker protocol versioning | PLANNED | `CORE-029` required. |
| Live Microsoft 365 egress | BLOCKED | `browser-internal` is Docker `internal: true`; worker has private ingress but no viable outbound Microsoft path. `CORE-025` mandatory. |
| Sanitized errors | IMPLEMENTED_NOT_ATTESTED | Stable error mapping/redaction exists. |

## Planner domain

| Capability | State | Baseline interpretation |
|---|---|---|
| Plans/projects | IMPLEMENTED_MOCK_ONLY | `planner_plan_list/get` have mock behavior; live worker returns placeholder empty/null results. |
| Tasks/WBS | IMPLEMENTED_MOCK_ONLY | `planner_task_list/get` have mock behavior only. |
| Project snapshot | IMPLEMENTED_MOCK_ONLY | Composite mock-safe read only. |
| Buckets | SPECIFIED_ONLY | Capability metadata/domain skeleton exists; no independently implemented live path. |
| Assignments/resources | SPECIFIED_ONLY | Capability/domain representation only. |
| Dependencies incl. FS/SS/SF/FF | SPECIFIED_ONLY | Domain/capability specification exists; no real UI implementation. |
| Milestones | PLANNED | No real baseline implementation. |
| Duration/effort | SPECIFIED_ONLY | Documented/domain-planned only. |
| Gantt/timeline | PLANNED | No real baseline implementation. |
| Critical path | PLANNED | No real baseline implementation. |
| Workload | SPECIFIED_ONLY | Capability/domain intent exists; no live implementation. |
| Goals | SPECIFIED_ONLY | Capability/domain skeleton only. |
| Sprints/backlog | SPECIFIED_ONLY | Capability/domain skeleton only. |
| Custom fields | SPECIFIED_ONLY | Capability/domain skeleton only. |
| Conditional formatting | PLANNED | No baseline implementation. |
| Calendars | PLANNED | No baseline implementation. |
| History/conversations | PLANNED | No baseline implementation. |
| Portfolios/roadmaps | SPECIFIED_ONLY | Capability/domain skeleton only. |
| Sharing/memberships | PLANNED | No baseline implementation. |
| Import/export | PLANNED | No baseline implementation. |
| Reporting/analytics | SPECIFIED_ONLY | Reporting scaffolding/docs exist; no live Planner analytics implementation. |

## Architectural reconciliation decisions

- Global UIContract attestation: `STILL_REQUIRED` redesign into fragments.
- Scoped Capability Registry: `STILL_REQUIRED`.
- Metadata-driven policy via Canonical Tool Registry: `STILL_REQUIRED`.
- Typed closed worker protocol: `STILL_REQUIRED`.
- True browser readiness/lifespan ownership: `STILL_REQUIRED`.
- Private ingress + controlled egress: `REQUIRES_REDESIGN` because current `internal: true` network blocks live Microsoft egress.
- Generalized M365 state identity: `STILL_REQUIRED`.
- Existing `planner_*` public tool names: `PRESERVE`.
- Existing no-raw-browser/no-session-export security boundary: `ALREADY_IMPLEMENTED` as an invariant to preserve.
