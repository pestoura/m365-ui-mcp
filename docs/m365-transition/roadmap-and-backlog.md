# m365-ui-mcp — Roadmap and Transition Backlog

Status: **PLANNED / CANONICAL TRANSITION PROGRAM DRAFT**

## 1. Backlog preservation rule

The existing Planner backlog keys `P-001..P-074` remain historically and semantically stable.

They are not renumbered or silently redefined as generic M365 tasks.

New namespaces:

```text
M365-SETUP-*   transition/setup and rename
CORE-*         shared M365 platform/core
PLN-MIG-*      Planner adapter migration/parity work
OUT-*          Outlook product capabilities
XAPP-*         cross-application execution
REL-*          M365 release/acceptance
```

If Phase 0 discovers that the Planner project has already introduced additional canonical IDs, this document must be reconciled without stealing/reusing them.

## 2. Advancement rule

Work advances automatically while required gates are PASS/GREEN.

Stop only for a real blocker such as:

- current Planner cycle not yet complete;
- unresolved repository-state ambiguity;
- failed security/CI gate;
- live authentication/MFA required;
- Conditional Access blocker;
- missing UI evidence/attestation;
- destructive/high-risk operation requiring explicit approval;
- privacy/session-boundary conflict;
- ambiguous mutation outcome;
- external Microsoft service unavailable;
- capability absent in target tenant.

A gate that did not execute is not green.

---

# PHASE 0 — Final Planner discovery and transition baseline

Objective: determine what the Planner actually became before touching architecture/naming.

### `M365-SETUP-001` — Freeze transition entry window

- confirm current Planner autonomous cycle has ended;
- ensure expected merges are complete;
- identify any legitimate remaining active branches/PRs;
- record entry timestamp.

Gate: no hidden in-flight Planner merge expected.

### `M365-SETUP-002` — Capture final repository state

Produce final-state evidence containing:

- `main` SHA/version;
- branches/PRs;
- tags/releases;
- contracts/schema versions;
- package/deployment state;
- CI/release gate state.

### `M365-SETUP-003` — Implementation/specification inventory

Classify every subsystem/capability:

```text
IMPLEMENTED_LIVE
IMPLEMENTED_MOCK_ONLY
IMPLEMENTED_NOT_ATTESTED
SPECIFIED_ONLY
PLANNED
DEPRECATED
BLOCKED
```

### `M365-SETUP-004` — Public Planner tool compatibility inventory

Record every existing tool contract and mark:

```text
PRESERVE
VERSION
DEPRECATE_LATER
INTERNAL_ONLY
```

Default = `PRESERVE`.

### `M365-SETUP-005` — Security-invariant verification

Re-run and evidence all current Planner security/runtime invariants.

### `M365-SETUP-006` — Live topology/egress assessment

Prove browser-worker access to Microsoft while maintaining no public worker ingress.

### `M365-SETUP-007` — Create pre-M365 Planner baseline tag

Tag exact final Planner state after applicable gates pass.

### `M365-SETUP-008` — Reconcile transition blueprint

Rebase/merge this documentation against final `main`; classify every proposed migration item as:

```text
STILL_REQUIRED
ALREADY_IMPLEMENTED
SUPERSEDED
REQUIRES_REDESIGN
```

### `M365-SETUP-009` — Rename impact map

Inventory all repository/package/deployment/config/portal/monitoring references.

### `M365-SETUP-010` — Authorize transition

Formal go/no-go gate for Phase 1.

---

# PHASE 1 — Product identity and shared-core extraction

Objective: convert Planner-specific platform infrastructure into M365 core without changing Planner behavior.

### `CORE-001` — Product/repository identity ADR

Accept `m365-ui-mcp` scope and naming, with Planner + Outlook as initial application modules.

### `CORE-002` — Repository rename

Rename:

```text
pestoura/planner-mcp
-> pestoura/m365-ui-mcp
```

Only after Phase 0 gates.

### `CORE-003` — Python package namespace migration

Target:

```text
planner_mcp core -> m365_mcp
planner_browser_worker -> m365_browser_worker
```

Preserve Planner tool semantics and introduce compatibility imports only where useful and bounded.

### `CORE-004` — Configuration namespace migration

Canonical new prefix:

```text
M365_*
```

Temporary compatibility:

```text
PLANNER_* -> mapped aliases with deprecation metadata
```

No credential-shaped environment variables permitted.

### `CORE-005` — Generic control-plane package boundary

Separate generic control plane from Planner domain implementation.

### `CORE-006` — Generic browser-worker package boundary

Move Playwright/session lifecycle to application-neutral worker core.

### `CORE-007` — Application Registry

Register enabled modules:

```text
planner
outlook
```

No plugin may self-register without schema/registry validation.

### `CORE-008` — Canonical Tool Registry

Implement metadata-driven registry and remove static tool-name policy coupling.

### `CORE-009` — Dynamic MCP tool registration

Generate/register public semantic surface from validated application definitions/manifests.

### `CORE-010` — Tool profiles/projections

Support bounded exposure profiles to reduce schema/token footprint, e.g.:

```text
full
planner
outlook
read-only
```

Projection affects exposure, never silently weakens policy.

Gate for Phase 1: all pre-transition Planner contract/tests remain GREEN.

---

# PHASE 2 — Capability and UI contract redesign

### `CORE-011` — Scoped Capability Registry

Add app/surface/account/container scope.

### `CORE-012` — Effective capability projection

Combine registry + auth + account context + UI evidence + runtime health + policy.

### `CORE-013` — Fragmented UIContract storage

Split global contract by common/app/surface capability fragments.

### `CORE-014` — Per-fragment attestation

One UI drift must only degrade dependent capabilities.

### `CORE-015` — Contract-set digest

Every execution records the exact UIContract fragment set/digest used.

### `CORE-016` — Locator strategy abstraction

Prioritize ARIA/accessible semantics; stable fallback selectors only with evidence.

### `CORE-017` — UI drift lifecycle

Support:

```text
HEALTHY
STALE
DRIFTED
RE_ATTESTATION_REQUIRED
```

and automated dependent-capability degradation.

### `CORE-018` — Capability evidence persistence

Persist evidence metadata/digests without tenant content.

### `CORE-019` — Attestation tooling/runbook

Deterministic discovery/attestation workflow, never CI against real tenant.

### `CORE-020` — Capability expiration/revalidation

Evidence lifetime and re-attestation policy.

---

# PHASE 3 — Browser/session worker hardening

### `CORE-021` — FastAPI lifespan browser ownership

Worker startup/stop must explicitly own Playwright + Chromium lifecycle.

### `CORE-022` — True liveness vs readiness

Readiness proves browser/profile/protocol/contract/lock subsystems.

### `CORE-023` — Session/Capability Broker

Bind semantic authorization to existing professional browser session without exporting cookies/tokens.

### `CORE-024` — Account-context enforcement

Fail closed on ambiguous/wrong professional context.

### `CORE-025` — Controlled worker egress

Private control-plane network plus outbound Microsoft connectivity without public worker route.

### `CORE-026` — Profile-level serialized executor

One active browser operation per profile initially; bounded queue and `WORKER_BUSY` behavior.

### `CORE-027` — Page lifecycle isolation

Operation-scoped pages where practical; no accidental cross-operation state bleed.

### `CORE-028` — Typed worker operation protocol

Closed operation enum/envelopes; no generic browser endpoint.

### `CORE-029` — Worker protocol version negotiation

Fail closed on incompatible control-plane/worker versions.

### `CORE-030` — Worker error taxonomy expansion

Preserve sanitized errors and add app/capability-safe mapping.

---

# PHASE 4 — Governance, state and execution plane

### `CORE-031` — Metadata-driven policy engine

Policy consumes Tool Registry metadata instead of hardcoded name sets.

### `CORE-032` — Security tier model

Implement T0..T4 or final approved equivalent.

### `CORE-033` — Scope-aware policy

Application/mailbox/resource scope becomes first-class policy input.

### `CORE-034` — Per-node BATCH/DAG/RUNBOOK policy

No aggregate authorization shortcut.

### `CORE-035` — Approval plan digest

Canonical immutable digest for multi-node mutating plans.

### `CORE-036` — Atomic approval consumption

Persistent, single-use, replay-safe approval.

### `CORE-037` — Generalized state identity

Move from Planner-only external-id assumptions to app/container/resource identity.

### `CORE-038` — Idempotency/replay protection v2

Operation/result association plus read-back-aware retry rules.

### `CORE-039` — Typed locks

Account/profile/application/container/resource locks as needed.

### `CORE-040` — Saga/checkpoint generalization

Cross-app-safe execution lifecycle.

### `CORE-041` — Compensation registry

Explicit compensation availability/strategy per mutation.

### `CORE-042` — `INDETERMINATE` terminal state

Required for mutations whose resulting Microsoft state cannot be proven.

### `CORE-043` — Dry-run/policy simulation

Return per-node policy outcomes without mutation.

---

# PHASE 5 — Result shaping, provenance and observability

### `CORE-044` — Result projection operators

Support typed bounded:

```text
fields/select
count
exists
first
latest
top_n
pagination
metadata_only
```

### `CORE-045` — Artifact/evidence references

Large outputs stored/referenced according to privacy classification and retention policy.

### `CORE-046` — Secret-aware result fields

Classify PUBLIC/INTERNAL/SENSITIVE/SECRET; SECRET never serialized.

### `CORE-047` — Execution provenance envelope

Include tool/version, execution id, application, capability/contract digests, timestamp/result digest.

### `CORE-048` — Token/context economics metrics

Measure direct execution ratio, round-trips avoided and result reduction.

### `CORE-049` — UI execution metrics

Latency/outcome per semantic operation with low-cardinality labels.

### `CORE-050` — Drift/read-back/indeterminate metrics

Operational quality metrics without tenant-content labels.

---

# PHASE 6 — Planner adapter migration/parity

Objective: prove the generalized platform with the application that created it.

### `PLN-MIG-001` — Move Planner semantic schemas into app module

### `PLN-MIG-002` — Move Planner Tool Registry entries

### `PLN-MIG-003` — Move Planner capability definitions

### `PLN-MIG-004` — Split Planner UIContract fragments

### `PLN-MIG-005` — Move Planner worker operations into adapter

### `PLN-MIG-006` — Preserve `planner_*` public tool names

### `PLN-MIG-007` — Reconcile all final P-001..P-074 implementation state

### `PLN-MIG-008` — Mock parity suite

Before/after normalized outputs must match for unchanged contracts.

### `PLN-MIG-009` — Policy parity suite

No Planner operation becomes less governed after extraction.

### `PLN-MIG-010` — Live read parity/attestation

Where final Planner baseline already had supported live reads, demonstrate equivalent behavior.

### `PLN-MIG-011` — Mutation parity

Only applicable if Planner cycle has already promoted writes by transition time.

### `PLN-MIG-012` — Planner migration acceptance gate

Outlook implementation cannot proceed to governed live mutations until Planner parity is GREEN.

---

# PHASE 7 — Outlook Foundation / discovery / read-only

## Platform and discovery

### `OUT-001` — Outlook application module skeleton
### `OUT-002` — Outlook mock UI/test fixture foundation
### `OUT-003` — Outlook shell/navigation contracts
### `OUT-004` — Outlook capability discovery model
### `OUT-005` — Primary-mailbox context verification
### `OUT-006` — Shared-mailbox scoped context model
### `OUT-007` — Outlook readiness/smoke extension

## Mail reads

### `OUT-010` — Message list
### `OUT-011` — Message get/read
### `OUT-012` — Advanced mail search
### `OUT-013` — Conversation/thread reads
### `OUT-014` — Attachment metadata/list
### `OUT-015` — Controlled attachment retrieval boundary
### `OUT-016` — Folder listing/navigation reads
### `OUT-017` — Category listing/read state
### `OUT-018` — Flag/follow-up read state
### `OUT-019` — Pin/Snooze read state

## Calendar reads

### `OUT-020` — Calendar list
### `OUT-021` — Event list/get/search
### `OUT-022` — Availability/free-busy reads
### `OUT-023` — Scheduling Assistant structural reads
### `OUT-024` — Shared-calendar reads

## People/To Do reads

### `OUT-025` — People/contact search/get
### `OUT-026` — Directory/org-context reads
### `OUT-027` — Contact-list reads
### `OUT-028` — To Do list/task reads
### `OUT-029` — My Day/smart-list reads

Gate: authenticated Outlook read-only acceptance with no mailbox mutation.

---

# PHASE 8 — Outlook safe organization mutations

### `OUT-030` — Mark read/unread
### `OUT-031` — Category create/update/delete governance
### `OUT-032` — Category apply/remove/bulk
### `OUT-033` — Flag/unflag/complete
### `OUT-034` — Follow-up due/reminder
### `OUT-035` — Pin/unpin
### `OUT-036` — Snooze/unsnooze
### `OUT-037` — Archive/restore
### `OUT-038` — Move message
### `OUT-039` — Folder create/rename/favorite
### `OUT-040` — Focused/Other movement

Every mutation requires read-back acceptance before promotion.

---

# PHASE 9 — Drafting and outbound mail

### `OUT-041` — Draft create/get/update/discard
### `OUT-042` — Recipient resolution (To/CC/BCC)
### `OUT-043` — From identity selection
### `OUT-044` — Draft attachments
### `OUT-045` — Importance/sensitivity options
### `OUT-046` — Signature integration
### `OUT-047` — Template/snippet integration
### `OUT-048` — Read/delivery receipt options
### `OUT-049` — Schedule send
### `OUT-050` — Send draft
### `OUT-051` — Reply
### `OUT-052` — Reply all
### `OUT-053` — Forward
### `OUT-054` — Resend
### `OUT-055` — Sent-item read-back/idempotency strategy
### `OUT-056` — Recall
### `OUT-057` — Recall-status reporting

Outbound operations default to governed/HITL posture until explicitly relaxed by policy.

---

# PHASE 10 — Mail automation and settings

### `OUT-060` — Sweep discovery/manage
### `OUT-061` — Rule list/get
### `OUT-062` — Rule create/update/delete
### `OUT-063` — Rule enable/disable/order
### `OUT-064` — Stop-processing/conditions/actions/exceptions
### `OUT-065` — Quick Step list/get
### `OUT-066` — Quick Step create/update/delete
### `OUT-067` — Quick Step execution policy expansion
### `OUT-068` — Conditional formatting manage
### `OUT-069` — Mail forwarding settings
### `OUT-070` — Undo Send settings
### `OUT-071` — View/Focused/conversation settings
### `OUT-072` — Notification settings
### `OUT-073` — Signature management
### `OUT-074` — Full mail template management
### `OUT-075` — My Templates/snippets

---

# PHASE 11 — Calendar write/scheduling

### `OUT-080` — Appointment create/update/delete
### `OUT-081` — Meeting create/update
### `OUT-082` — Attendee/optional/resource management
### `OUT-083` — Teams meeting option
### `OUT-084` — Recurrence/occurrence/series handling
### `OUT-085` — Reminder/category/private/show-as
### `OUT-086` — Meeting accept/tentative/decline
### `OUT-087` — Response with message
### `OUT-088` — Propose new time
### `OUT-089` — Forward meeting
### `OUT-090` — Cancel meeting
### `OUT-091` — Organizer response tracking
### `OUT-092` — Find common slot
### `OUT-093` — Room/resource search
### `OUT-094` — Scheduling Poll create/manage/results
### `OUT-095` — Shared-calendar add/remove
### `OUT-096` — Calendar permission/delegation management
### `OUT-097` — Calendar publish/unpublish
### `OUT-098` — Working hours/time zone/work-location settings

---

# PHASE 12 — People, To Do and shared mailboxes

## People

### `OUT-100` — Contact create/update/delete
### `OUT-101` — Contact categories/favorites
### `OUT-102` — Contact-list create/update/delete
### `OUT-103` — Contact-list membership

## To Do

### `OUT-104` — Task create/update/complete/delete
### `OUT-105` — Due date/reminder/recurrence
### `OUT-106` — Important/My Day
### `OUT-107` — Task steps
### `OUT-108` — Notes/attachments
### `OUT-109` — Flagged-email relationship
### `OUT-110` — Email-to-task composite

## Shared mailboxes

### `OUT-111` — Shared-mailbox discovery/open
### `OUT-112` — Shared-mailbox scoped search/read
### `OUT-113` — Shared categories/flags/folders
### `OUT-114` — Shared-mailbox rules
### `OUT-115` — Shared automatic replies
### `OUT-116` — Send-as
### `OUT-117` — Send-on-behalf
### `OUT-118` — Shared-calendar linkage
### `OUT-119` — Explicit capability-difference reporting

---

# PHASE 13 — Security/compliance-visible Outlook features

### `OUT-120` — Junk/not-junk reporting
### `OUT-121` — Phishing reporting
### `OUT-122` — Block/safe sender management
### `OUT-123` — Block/safe domain management
### `OUT-124` — Sensitivity/security status reads
### `OUT-125` — Purview encryption options
### `OUT-126` — S/MIME capability/status
### `OUT-127` — S/MIME sign/encrypt operations where safely available
### `OUT-128` — Retention/archive policy-visible controls
### `OUT-129` — Compliance blocker/error mapping

No control may bypass tenant compliance/security policy.

---

# PHASE 14 — OOO, polls, groups and advanced Outlook surfaces

### `OUT-130` — Automatic reply read/configure
### `OUT-131` — Internal/external OOO messages
### `OUT-132` — OOO schedule
### `OUT-133` — OOO calendar block
### `OUT-134` — OOO decline new invitations
### `OUT-135` — OOO cancel existing meetings
### `OUT-136` — Email poll create/manage/results
### `OUT-137` — M365 Group discovery/reads
### `OUT-138` — Group calendar/mail interaction review
### `OUT-139` — Group membership governance if brought in scope
### `OUT-140` — Specific add-in capability framework (no generic add-in executor)

---

# PHASE 15 — Composite execution and token reduction

### `XAPP-001` — DIRECT executor contract
### `XAPP-002` — BATCH request contract
### `XAPP-003` — Bounded BATCH scheduler
### `XAPP-004` — Per-node policy/approval/evidence
### `XAPP-005` — DAG contract
### `XAPP-006` — DAG cycle validation/topological scheduler
### `XAPP-007` — Typed output/input bindings
### `XAPP-008` — Cancellation/deadline propagation
### `XAPP-009` — Long-run checkpoint/resume
### `XAPP-010` — Dead-letter/manual-intervention state
### `XAPP-011` — Runbook registry/versioning
### `XAPP-012` — Runbook canonical serialization/digest
### `XAPP-013` — Runbook promotion process
### `XAPP-014` — HYBRID escalation policy
### `XAPP-015` — Agentic token/runtime budgets
### `XAPP-016` — Minimum-context escalation shaping

Composite product operations:

### `XAPP-020` — Outlook inbox digest
### `XAPP-021` — Outlook mail triage
### `XAPP-022` — Outlook person context
### `XAPP-023` — Outlook daily work context
### `XAPP-024` — M365 batch across Planner + Outlook
### `XAPP-025` — M365 DAG across Planner + Outlook
### `XAPP-026` — Meeting preparation runbook
### `XAPP-027` — Project/mail follow-up runbook
### `XAPP-028` — Daily M365 context runbook

---

# PHASE 16 — Acceptance, hardening and release

### `REL-001` — Complete threat-model update for M365 scope
### `REL-002` — Trust-boundary review
### `REL-003` — Privacy/data-retention review for mailbox/calendar/contact content
### `REL-004` — Container hardening parity with Planner/Hermes baseline
### `REL-005` — Egress-control acceptance
### `REL-006` — Tool Registry schema/consistency tests
### `REL-007` — Capability/UIContract consistency gates
### `REL-008` — Policy metadata completeness gate
### `REL-009` — No generic browser-operation regression test
### `REL-010` — Secret/session exfiltration regression suite
### `REL-011` — Mock/isolated acceptance suite
### `REL-012` — Planner parity acceptance
### `REL-013` — Outlook read-only live acceptance
### `REL-014` — Outlook safe-write live acceptance
### `REL-015` — Governed outbound-mail acceptance
### `REL-016` — Calendar governed-write acceptance
### `REL-017` — BATCH/DAG policy isolation acceptance
### `REL-018` — Result-shaping/token-economics benchmark
### `REL-019` — Failure/timeout/read-back ambiguity fault injection
### `REL-020` — Documentation/traceability closure
### `REL-021` — Release candidate
### `REL-022` — Production rollout plan
### `REL-023` — Rollback/compatibility validation
### `REL-024` — `m365-ui-mcp` 1.0.0 production-readiness decision

---

# 17. Proposed release bands

Release numbers are planning bands, not support claims.

| Band | Primary outcome |
|---|---|
| `0.1.x-transition` | Phase 0 baseline + architecture reconciliation |
| `0.2.x-core` | generic M365 core + Planner parity |
| `0.3.x-outlook-read` | Outlook discovery/read-only |
| `0.4.x-outlook-safe-write` | categories/flags/folders/organization |
| `0.5.x-outlook-mail` | drafts/outbound/recall/templates/rules |
| `0.6.x-calendar` | calendar/scheduling/meeting writes |
| `0.7.x-people-todo-shared` | People/To Do/shared mailboxes |
| `0.8.x-execution-plane` | BATCH/DAG/RUNBOOK/result shaping |
| `0.9.x-hardening` | security/resilience/acceptance/observability |
| `1.0.0` | evidence-backed production-ready Planner + Outlook M365 UI MCP |

Actual version mapping must respect the final Planner version found during Phase 0.

# 18. Definition of transition success

The transition is successful when:

- repository/product identity is `m365-ui-mcp`;
- existing Planner functionality is preserved or explicitly versioned;
- Planner and Outlook share one hardened M365 control-plane/browser foundation;
- Outlook capability state is evidence-driven and scope-aware;
- no generic browser primitive is exposed;
- deterministic operations bypass unnecessary intermediate LLM hops;
- DIRECT/BATCH/DAG/RUNBOOK are governed by per-node policy;
- outbound/destructive operations remain approval-controlled according to policy;
- every UI mutation has a read-back/uncertainty strategy;
- UI drift degrades only dependent capabilities;
- result shaping prevents avoidable context explosion;
- observability can quantify direct-execution ratio, round-trip reduction and result reduction;
- the browser session never becomes exposed as a reusable credential to MCP clients.
