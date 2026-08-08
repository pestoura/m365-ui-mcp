# Planner MCP — Planner Premium Capability Matrix

Status: specification and canonical evidence register.
Canonical upstream: [docs/vision.md](./vision.md)
Related: [docs/architecture.md](./architecture.md) · [docs/security.md](./security.md) · [docs/privacy-boundary.md](./privacy-boundary.md) · [docs/governance.md](./governance.md) · [docs/ui-contract.md](./ui-contract.md) · [docs/browser-worker.md](./browser-worker.md) · [docs/tool-catalog.md](./tool-catalog.md) · [docs/authentication-and-mfa.md](./authentication-and-mfa.md)

Requirement IDs (`CAP-xxx`) are stable, never reused, never renumbered.

---

## 1. Status of this document

**CAP-001 — This is the canonical browser-evidence capability matrix.** It is the single place
where support for a Planner Premium capability is asserted. Any other document, README, issue or
message that claims support is subordinate to this matrix.

**CAP-002 — Microsoft Graph availability is explicitly irrelevant to support decisions.** Graph is
neither a gate, a substitute, nor evidence. A capability present in Graph but not observed and
attested in the browser surface is **not supported**. A capability absent from Graph but attested
in the browser surface **is** eligible for support (`ARCH-002`, vision: Graph is not a functional
gate).

**CAP-003 — Support is browser evidence only.** The evidence chain is: tenant/licence observation →
UI observation → UIContract attestation → validated READ → validated MUTATION → governance
decision (`UI-041`, `GOV-010`).

**CAP-004 — No invented tenant facts.** No row below asserts what the operator's tenant or licence
contains. Every tenant/licence and UI cell is `UNVERIFIED_LIVE` because this repository contains no
live observation. Filling a cell requires a recorded attestation artefact, not an assumption
(`GOV-000`, `GOV-052`).

**CAP-005 — Current release performs no mutations** (`SEC-007`); therefore no row can legitimately
reach `MUTATION_ATTESTED` today.

---

## 2. Column definitions

| Column | Meaning |
| --- | --- |
| `CAP-ID` | Stable requirement ID for the capability row |
| Capability / domain | The Planner Premium function, grouped by domain |
| Tenant / licence observed | Whether the tenant and licence signals enabling this capability have been observed live; `UNVERIFIED_LIVE` until observed |
| UI observed | Whether the corresponding UI surface/affordance has been seen live (`DISCOVERED`) |
| UIContract attestation | Attestation state of the backing contract entries (`UI-041`) |
| READ validated | Whether a semantic read returned structurally valid data confirmed by a read-back probe |
| MUTATION validated | Whether a governed mutation took effect and was confirmed by read-back, with compensation demonstrated |
| Support state | Published support decision (`CAP-030`) |
| Required policy / mutation class | Minimum mutation class and approval posture (`SEC-020`) |
| Read-back strategy | How the postcondition is verified for this capability |
| Drift / failure behaviour | What happens when the contract drifts or verification fails |
| Evidence / notes | Pointer to sanitized evidence; scope notes |

**CAP-010 — Cell vocabulary.** Tenant/licence and UI cells: `UNVERIFIED_LIVE`, `OBSERVED`,
`ABSENT`. Attestation cells: the `UI-041` states. READ/MUTATION cells: `NO`, `YES`, `BLOCKED`.
Nothing else is written.

**CAP-011 — `ABSENT` is a live observation too**, and requires the same evidence discipline as
`OBSERVED`. Never inferred from documentation or from Graph.

---

## 3. Support states

**CAP-030 — Support state vocabulary.**

| State | Meaning |
| --- | --- |
| `UNVERIFIED_LIVE` | Default. No live evidence exists. Not supported, not claimed. |
| `DISCOVERED` | Surface observed to exist; no attested contract entry. |
| `READ_SUPPORTED` | Reads are attested and published; mutations not available. |
| `MUTATION_SUPPORTED` | Governed mutations attested and published. |
| `DEGRADED` | Previously supported, currently failing verification (`GOV-012`). |
| `BLOCKED` | Structurally unavailable: Conditional Access blocker, licence absent, or policy refusal. |
| `OUT_OF_SCOPE` | Deliberately not pursued in this product. |

**CAP-031** A capability may only be described as supported when its row says `READ_SUPPORTED` or
`MUTATION_SUPPORTED`. Any other state is described as unsupported (`GOV-090`).

**CAP-032** Regression is automatic: failed live verification or `UI_DRIFT` moves the row to
`DEGRADED` (or `BLOCKED` for a Conditional Access blocker, `AUTH-070`) without a human decision.

---

## 4. Matrix — Part A: evidence

All rows are `UNVERIFIED_LIVE` because this repository contains no live tenant evidence (`CAP-004`).

| CAP-ID | Capability / domain | Tenant / licence observed | UI observed | UIContract attestation | READ validated | MUTATION validated | Support state |
| --- | --- | --- | --- | --- | --- | --- | --- |
| **CAP-100** | Plans / projects (list, open, metadata) | UNVERIFIED_LIVE | UNVERIFIED_LIVE | UNVERIFIED_LIVE | NO | NO | UNVERIFIED_LIVE |
| **CAP-101** | WBS: summary tasks and subtasks / hierarchy | UNVERIFIED_LIVE | UNVERIFIED_LIVE | UNVERIFIED_LIVE | NO | NO | UNVERIFIED_LIVE |
| **CAP-102** | Buckets | UNVERIFIED_LIVE | UNVERIFIED_LIVE | UNVERIFIED_LIVE | NO | NO | UNVERIFIED_LIVE |
| **CAP-103** | Assignments (task ↔ person) | UNVERIFIED_LIVE | UNVERIFIED_LIVE | UNVERIFIED_LIVE | NO | NO | UNVERIFIED_LIVE |
| **CAP-104** | Dependencies FS / SS / SF / FF | UNVERIFIED_LIVE | UNVERIFIED_LIVE | UNVERIFIED_LIVE | NO | NO | UNVERIFIED_LIVE |
| **CAP-105** | Milestones | UNVERIFIED_LIVE | UNVERIFIED_LIVE | UNVERIFIED_LIVE | NO | NO | UNVERIFIED_LIVE |
| **CAP-106** | Duration and effort fields | UNVERIFIED_LIVE | UNVERIFIED_LIVE | UNVERIFIED_LIVE | NO | NO | UNVERIFIED_LIVE |
| **CAP-107** | Timeline / Gantt view | UNVERIFIED_LIVE | UNVERIFIED_LIVE | UNVERIFIED_LIVE | NO | NO | UNVERIFIED_LIVE |
| **CAP-108** | Critical path | UNVERIFIED_LIVE | UNVERIFIED_LIVE | UNVERIFIED_LIVE | NO | NO | UNVERIFIED_LIVE |
| **CAP-109** | People view / workload | UNVERIFIED_LIVE | UNVERIFIED_LIVE | UNVERIFIED_LIVE | NO | NO | UNVERIFIED_LIVE |
| **CAP-110** | Goals | UNVERIFIED_LIVE | UNVERIFIED_LIVE | UNVERIFIED_LIVE | NO | NO | UNVERIFIED_LIVE |
| **CAP-111** | Sprints and backlog | UNVERIFIED_LIVE | UNVERIFIED_LIVE | UNVERIFIED_LIVE | NO | NO | UNVERIFIED_LIVE |
| **CAP-112** | Custom fields | UNVERIFIED_LIVE | UNVERIFIED_LIVE | UNVERIFIED_LIVE | NO | NO | UNVERIFIED_LIVE |
| **CAP-113** | Conditional colouring / formatting rules | UNVERIFIED_LIVE | UNVERIFIED_LIVE | UNVERIFIED_LIVE | NO | NO | UNVERIFIED_LIVE |
| **CAP-114** | Custom calendar / working time | UNVERIFIED_LIVE | UNVERIFIED_LIVE | UNVERIFIED_LIVE | NO | NO | UNVERIFIED_LIVE |
| **CAP-115** | Task history and conversations | UNVERIFIED_LIVE | UNVERIFIED_LIVE | UNVERIFIED_LIVE | NO | NO | UNVERIFIED_LIVE |
| **CAP-116** | Portfolios and roadmaps | UNVERIFIED_LIVE | UNVERIFIED_LIVE | UNVERIFIED_LIVE | NO | NO | UNVERIFIED_LIVE |
| **CAP-117** | Sharing and membership | UNVERIFIED_LIVE | UNVERIFIED_LIVE | UNVERIFIED_LIVE | NO | NO | UNVERIFIED_LIVE |
| **CAP-118** | Import / export | UNVERIFIED_LIVE | UNVERIFIED_LIVE | UNVERIFIED_LIVE | NO | NO | UNVERIFIED_LIVE |
| **CAP-119** | Reporting / analytics surfaces | UNVERIFIED_LIVE | UNVERIFIED_LIVE | UNVERIFIED_LIVE | NO | NO | UNVERIFIED_LIVE |

---

## 5. Matrix — Part B: policy, verification, failure

| CAP-ID | Required policy / mutation class | Read-back strategy | Drift / failure behaviour | Evidence / notes |
| --- | --- | --- | --- | --- |
| `CAP-100` | READ; creation would be `GOVERNED_WRITE` | Re-read the plan list/metadata and compare identity + field digest | `UI_DRIFT` → row `DEGRADED`, dependents refused | None recorded |
| `CAP-101` | READ; hierarchy changes `GOVERNED_WRITE` | Re-read parent/child relations for the affected subtree | Hierarchy mismatch → `UNVERIFIED`, no partial claim | None recorded |
| `CAP-102` | READ; bucket create/rename `SAFE_WRITE`; delete `DESTRUCTIVE` | Re-read bucket set and membership counts | Deletes additionally gated (`SEC-023`) | None recorded |
| `CAP-103` | READ; assign/unassign `GOVERNED_WRITE` | Re-read task assignees, compare opaque handles | Ambiguous person resolution fails closed | Person identity exposed only as opaque handle (`PRIV-063`) |
| `CAP-104` | READ; dependency edits `GOVERNED_WRITE` | Re-read predecessor/successor edges and link type | Wrong link type is a failure, never coerced | Link types must be distinguished, never defaulted to FS |
| `CAP-105` | READ; milestone flag `GOVERNED_WRITE` | Re-read the milestone attribute of the task | Ambiguity between zero-duration task and milestone fails closed | None recorded |
| `CAP-106` | READ; edits `GOVERNED_WRITE` | Re-read numeric fields with unit normalisation | Unit ambiguity fails closed | None recorded |
| `CAP-107` | READ (view-derived) | Structural read-back of the timeline rows, not pixels | View-only drift blocks derived reads | Never verified by screenshot (`PRIV-064`) |
| `CAP-108` | READ only; never computed locally and presented as Planner's | Re-read the product's own critical-path indication | Divergence between local computation and UI is reported, never reconciled silently | Local recomputation is not evidence |
| `CAP-109` | READ; workload changes via assignment class | Re-read workload aggregates | Aggregates are untrusted UI-derived data | None recorded |
| `CAP-110` | READ; goal edits `GOVERNED_WRITE` | Re-read goal linkage and progress fields | Licence-dependent surface; absence must be observed, not assumed | None recorded |
| `CAP-111` | READ; sprint moves `GOVERNED_WRITE` | Re-read sprint membership of affected items | Backlog/sprint mapping ambiguity fails closed | None recorded |
| `CAP-112` | READ; value edits `GOVERNED_WRITE`; schema edits `DESTRUCTIVE` | Re-read field definition and value | Field type changes are structural drift | None recorded |
| `CAP-113` | READ; rule edits `GOVERNED_WRITE` | Re-read rule definitions, not rendered colours | Colour is presentation; never used as evidence | None recorded |
| `CAP-114` | READ; calendar edits `GOVERNED_WRITE` | Re-read working-time definition | Timezone ambiguity fails closed | None recorded |
| `CAP-115` | READ only in this product | Re-read the latest history/conversation entry identifiers | Content is minimised and untrusted (`PRIV-061`) | Conversation content is prompt-injection surface |
| `CAP-116` | READ; portfolio edits `GOVERNED_WRITE` | Re-read portfolio membership | Cross-plan blast radius requires per-target locks | None recorded |
| `CAP-117` | `GOVERNED_WRITE` minimum; membership removal `DESTRUCTIVE` | Re-read membership and role | Access changes always require approval | Highest-risk domain |
| `CAP-118` | READ for export; import `DESTRUCTIVE` | Re-read the resulting objects, not the import report | Bulk operations are structural changes (`SEC-020`) | Export must not leave tenant content in the state store |
| `CAP-119` | READ | Re-read report parameters and row identifiers | Report numbers are untrusted UI-derived | None recorded |

---

## 6. Discovery and attestation workflow

**CAP-050 — Step 1: tenant/licence observation (read-only).** With an authenticated session
(`AUTH-020` = `AUTHENTICATED`) and a verified account context (`AUTH-030`), observe which
capability surfaces the tenant exposes. Record `OBSERVED` or `ABSENT` per row. No mutation, no
configuration change, no Graph call.

**CAP-051 — Step 2: UI discovery.** Navigate to the surface and confirm the affordance exists.
Row moves to `DISCOVERED`. Evidence: sanitized structural digest only (`UI-071`).

**CAP-052 — Step 3: contract entry + `UI_ATTESTED`.** Author the UIContract entry from the live
observation (never invented, `UI-002`), confirm unique resolution, expected role/text/structure.

**CAP-053 — Step 4: `READ_ATTESTED`.** Execute the semantic read through the normal path and
confirm the read-back probe. Only then may the row become `READ_SUPPORTED` after a governance
decision (`GOV-010`).

**CAP-054 — Step 5: `MUTATION_ATTESTED`.** Requires the mutation feature to exist, a policy
decision, an approval, a demonstrated compensation, and read-back confirmation. Not available in
the current release (`SEC-007`, `CAP-005`).

**CAP-055 — Step 6: publication.** A support state is published only by a reviewed change to this
matrix, referencing the attestation evidence (`GOV-050`).

**CAP-056 — Campaigns are read-only unless separately authorised**, run against a disposable or
explicitly authorised target, and never in CI (`GOV-042`, `ARCH-084`).

**CAP-057 — Blocked outcomes.** A Conditional Access managed-device requirement sets every
dependent row to `BLOCKED` with `BLOCKER_CONDITIONAL_ACCESS` and stops the campaign (`AUTH-070`,
`PRIV-020`).

**CAP-058 — Evidence hygiene.** Attestation artefacts contain no tenant content, no identity, no
screenshots, no URLs — only structural digests, states and timestamps (`PRIV-062`, `UI-070`).

**CAP-059 — Re-attestation cadence.** Rows expire per `UI-044`; an expired row reverts to the last
evidence-backed state, never remaining "supported" on stale evidence.

---

## 7. Consistency rules

**CAP-070** The matrix, the UIContract attestation states and `planner_capabilities` output must
agree. Disagreement is a release-blocking defect (`GOV-013`, `GOV-062`).

**CAP-071** A tool may not be published for a capability whose row is below `READ_SUPPORTED`
([docs/tool-catalog.md](./tool-catalog.md) `TOOL-060`).

**CAP-072** A test asserts that every capability key referenced by the contract or the tool catalog
exists as a `CAP-xxx` row here, and vice versa.

**CAP-073** A test asserts that no row claims support without a referenced evidence artefact.

---

## 8. Traceability

| ID range | Area |
| --- | --- |
| CAP-001…005 | Status and canonical role |
| CAP-010…011 | Cell vocabulary |
| CAP-030…032 | Support states |
| CAP-050…059 | Discovery and attestation workflow |
| CAP-070…073 | Consistency rules |
| CAP-100…119 | Capability rows |


