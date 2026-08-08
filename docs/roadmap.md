# Planner MCP Roadmap

This roadmap is normative for delivery sequencing. The canonical backlog is
[`docs/backlog.md`](backlog.md); this document does not redefine P-keys or EPIC ownership.

## 1. Product invariants

The roadmap must preserve these rules at every release:

- Planner Premium capabilities are implemented primarily through the private Chromium/Playwright
  browser worker. Microsoft Graph is optional context/optimisation and never a capability gate.
- The public MCP surface is semantic project-management API, never generic browser primitives.
- A capability is not reported as supported without tenant/UI evidence, an attested UIContract
  fragment and a viable read-back strategy.
- The personal-device boundary is fail-closed. Conditional Access that requires a managed,
  compliant, enrolled or certificate-backed device ends in `BLOCKER_CONDITIONAL_ACCESS`.
- MFA approval occurs only in Microsoft Authenticator.
- CI never performs a live Planner mutation.
- A gate that did not execute is not green.

See [`vision.md`](vision.md), [`architecture.md`](architecture.md),
[`privacy-boundary.md`](privacy-boundary.md), [`ui-contract.md`](ui-contract.md) and ADR-001..ADR-008.

## 2. Canonical EPIC map

| EPIC | Scope | Backlog |
| --- | --- | --- |
| EPIC-01 | Foundation | P-001..P-010 |
| EPIC-02 | Browser Worker / UI | P-011..P-017 |
| EPIC-03 | Authentication / MFA | P-018..P-024 |
| EPIC-04 | Read Model | P-025..P-030 |
| EPIC-05 | Mutations | P-031..P-036 |
| EPIC-06 | Scheduling / Project Management | P-037..P-045 |
| EPIC-07 | Reconciliation / Blueprints | P-046..P-053 |
| EPIC-08 | Reporting / Portfolio | P-054..P-060 |
| EPIC-09 | Security / Governance / Observability | P-061..P-067 |
| EPIC-10 | Acceptance / Release | P-068..P-074 |

This mapping is immutable unless a later ADR explicitly changes the product plan and updates
backlog, traceability, tests and release evidence in the same change.

## 3. Release 0.1.0 — Foundation + read-only

`0.1.0` is the first releasable contract. Its **registered MCP tool surface is read-only**.
The canonical public tools are:

1. `planner_health`
2. `planner_readiness`
3. `planner_capabilities`
4. `planner_agent_card`
5. `planner_ui_contract_status`
6. `planner_auth_status`
7. `planner_auth_start`
8. `planner_auth_resume`
9. `planner_auth_session_info`
10. `planner_plan_list`
11. `planner_plan_get`
12. `planner_task_list`
13. `planner_task_get`
14. `planner_project_snapshot`
15. `planner_account_context`
16. `planner_license_capabilities`
17. `planner_smoke_test`

All 17 tools are classified `READ` for this release. No task, bucket, dependency, scheduling,
sharing or reconciliation-apply mutation may be registered in the public MCP catalogue.

### 0.1.0 delivery scope

The release establishes:

- MCP runtime and Streamable HTTP control plane;
- versioned contracts, manifests and AgentCard;
- fail-closed configuration, policy and state foundations;
- structured logging, redaction and low-cardinality metrics;
- private FastAPI browser worker and Playwright/Chromium lifecycle;
- isolated persistent professional browser profile;
- formal authentication and MFA state detection;
- UIContract registry, attestation model and UI-drift fail-closed behaviour;
- plan/task/project read model and stable snapshot semantics;
- mock Planner UI and isolated browser acceptance;
- CI, dependency/secret/container scanning, CycloneDX SBOM and release evidence;
- complete canonical documentation and traceability.

### P-031 and P-050 in 0.1.0

The declared program critical path includes P-031 and P-050. This does **not** authorize a write
surface in 0.1.0.

- P-031 may land only as the internal mutation-safety framework (policy → approval → idempotency →
  typed lock → apply boundary → read-back → checkpoint), exercised against mocks and inaccessible
  from the 0.1.0 MCP registry.
- P-050 may land as reconciliation planning/diff/checkpoint infrastructure and mock-only execution.
  Tenant `apply` remains disabled and no `planner_project_reconcile` mutation is registered in
  0.1.0.

This distinction lets the safety architecture be proven before writes are exposed. A later release
must pass its own mutation acceptance gates before either path becomes externally callable.

## 4. Delivery order by EPIC

### EPIC-01 — Foundation (P-001..P-010)

Close the canonical specification, package/config/contracts/state foundations, Streamable HTTP
skeleton, redaction/metrics and typed error model. Documentation validation is blocking.

### EPIC-02 — Browser Worker / UI (P-011..P-017)

Build the internal worker, Playwright runtime, isolated professional profile, UIContract loader,
attestation/evidence workflow, drift detection and deterministic mock Planner UI. No public browser
primitive is introduced.

### EPIC-03 — Authentication / MFA (P-018..P-024)

Implement the formal auth state machine, interactive browser sign-in, MFA number-matching event,
Conditional Access blocker, session lifecycle, enrolment-prompt refusal and UI-observed account /
licence context. The password never enters the system.

### EPIC-04 — Read Model (P-025..P-030)

Implement plan list/detail, task list/detail, bucket/dependency reads and project snapshot. Reads are
normalized, schema-valid and evidence-bound. This EPIC closes the functional read-only surface of
0.1.0.

### EPIC-05 — Mutations (P-031..P-036)

First build the mutation framework in a dormant/mock-tested state. After 0.1.0, progressively expose
task, bucket, assignment and plan lifecycle mutations plus bulk-safety controls. Every mutation
requires policy, idempotency, lock, read-back and explicit handling of partial/unknown outcome.

### EPIC-06 — Scheduling / Project Management (P-037..P-045)

Add effort/duration, WBS hierarchy, FS/SS/SF/FF dependencies, milestones, timeline/Gantt, critical
path reads, people/workload, goals, sprints and backlog semantics only as UI evidence is obtained.

### EPIC-07 — Reconciliation / Blueprints (P-046..P-053)

Add custom fields/formatting/calendar capability work, stable identity bindings, desired-state
reconciliation, blueprint validation, dry-run planning and resumable runs. Live apply remains gated
until mutation attestation is complete.

### EPIC-08 — Reporting / Portfolio (P-054..P-060)

Add portfolio/roadmap reads, snapshot history, project/variance reporting, portfolio rollups,
sharing/permission governance, controlled export and governance reporting. Reporting consumes the
semantic read model; it never calls selectors directly.

### EPIC-09 — Security / Governance / Observability (P-061..P-067)

Complete default-deny policy, persistent single-use approvals, telemetry hygiene, hardened
containers, SBOM/vulnerability/digest gates, circuit breakers/retry policy and complete audit trail.
Security controls are required before write capability is promoted.

### EPIC-10 — Acceptance / Release (P-068..P-074)

Wire the complete CI pipeline, isolated acceptance IA-01..IA-16, live read-only acceptance,
traceability closure, documentation consistency and release gates. P-074 cuts `0.1.0` only when all
applicable required gates are green and no unsupported capability is presented as supported.

## 5. Critical path

The canonical program critical path is:

`P-001 → P-011 → P-014 → P-018 → P-025 → P-026 → P-027 → P-030 → P-031 → P-050 → P-069 → P-071 → P-073 → P-074`

| Key | Gate meaning on the critical path |
| --- | --- |
| P-001 | Canonical repository/specification/CI foundation |
| P-011 | Typed private browser-worker operation boundary |
| P-014 | Central UIContract and attestation gate |
| P-018 | Formal authentication state machine |
| P-025 | Plan/project list read |
| P-026 | Plan/project detail read |
| P-027 | Task list/detail read |
| P-030 | Composite project snapshot with stable hash |
| P-031 | Mutation-safety framework exists and is mock-tested; no 0.1 public write tool |
| P-050 | Reconciliation planning/checkpoint engine exists; live apply remains disabled in 0.1 |
| P-069 | Isolated acceptance IA-01..IA-16 |
| P-071 | Traceability matrix closure |
| P-073 | Release process and gates |
| P-074 | `0.1.0` release |

## 6. Releases after 0.1.0

Release numbers below are planning bands, not promises; capability promotion is evidence-driven.

| Band | Primary outcome |
| --- | --- |
| 0.2.x | authenticated live read, live UI attestation and hardened read operations |
| 0.3.x | first safe mutations and task/bucket CRUD with read-back |
| 0.4.x | dependencies, scheduling, milestones, WBS, goals and sprints |
| 0.5.x | desired-state reconciliation and blueprints with governed apply |
| 0.6.x | reporting, portfolio, workload and controlled export |
| 0.7–0.9.x | resilience, governance, observability and operational hardening |
| 1.0.0 | production-ready semantic Planner Premium MCP with complete evidence and acceptance |

A capability may move earlier or later only if the capability matrix, UI evidence and safety gates
support that decision. The absence or presence of a Microsoft Graph endpoint does not affect this
sequence.

## 7. Blockers and advancement rule

Normal implementation decisions do not stop the delivery loop. Work advances automatically while
its required gates are green. Stop only for a real blocker: manual authentication/MFA, Conditional
Access, risk approval, unavailable external service, rate limit, destructive operation not already
authorized, missing evidence, or a privacy/security-boundary conflict.

Known release blockers are recorded explicitly; they are never converted into a false PASS.
