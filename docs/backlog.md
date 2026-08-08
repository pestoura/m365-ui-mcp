# Backlog

Stable issue keys `P-001..P-074` across `EPIC-01..EPIC-10`. Keys are immutable: they are
referenced by GitHub issues, [traceability.md](traceability.md) and commit messages.

Each item states: **Objective**, **Scope**, **Acceptance**, **Tests/gates**, **Depends**,
**Evidence**.

Dependencies use zero-padded keys. `—` means no predecessor inside this backlog.

## Critical path

`P-001 → P-011 → P-014 → P-018 → P-025 → P-026 → P-027 → P-030 → P-031 → P-050 → P-069 → P-071 → P-073 → P-074`

## Epic index

| Epic | Title | Keys |
| --- | --- | --- |
| EPIC-01 | Foundation | P-001..P-010 |
| EPIC-02 | Browser worker & UI contract | P-011..P-017 |
| EPIC-03 | Authentication & MFA | P-018..P-024 |
| EPIC-04 | Read model | P-025..P-030 |
| EPIC-05 | Mutations | P-031..P-036 |
| EPIC-06 | Scheduling & PM semantics | P-037..P-045 |
| EPIC-07 | Reconciliation & blueprints | P-046..P-053 |
| EPIC-08 | Reporting & portfolio | P-054..P-060 |
| EPIC-09 | Security, governance & observability | P-061..P-067 |
| EPIC-10 | Acceptance & release | P-068..P-074 |

---

## EPIC-01 — Foundation

### P-001 — Repository, specification and CI foundation
- **Objective:** Establish the canonical specification, governance and CI baseline (this block).
- **Scope:** README, all `docs/*.md`, ADR-001..008, backlog, repo hygiene files, issue/PR
  templates, CI workflow skeleton with compile/lint/type/test/schema/secret/dependency/SBOM gates.
- **Acceptance:** Every required document exists and is specific; CI workflow present; no secrets
  committed; branch merged via PR.
- **Tests/gates:** ruff, mypy, pytest, schema validation, secret scan, `python -m compileall`.
- **Depends:** —
- **Evidence:** PR URL, CI run, commit list.

### P-002 — Python 3.12 project skeleton and packaging
- **Objective:** `src/`-layout package with pinned toolchain and reproducible install.
- **Scope:** `pyproject.toml` (project metadata, ruff, mypy, pytest config), package `planner_mcp`
  with `control_plane`, `worker`, `browser`, `policy`, `state` subpackages, dev extras.
- **Acceptance:** `pip install -e .[dev]` succeeds on 3.12; import of the package works; ruff and
  mypy configured strictly for `src/`.
- **Tests/gates:** build gate, lint, type.
- **Depends:** P-001
- **Evidence:** CI job log for install + lint + type.

### P-003 — Typed configuration and fail-closed startup
- **Objective:** Validated settings model; refuse to start on invalid/missing config.
- **Scope:** Pydantic settings, non-secret env only, explicit rejection of any credential-looking
  variable, redaction on display, readiness exposure.
- **Acceptance:** Missing required value ⇒ process exits non-zero with a typed error; no value is
  printed unredacted.
- **Tests/gates:** unit tests for valid/invalid/secret-shaped config.
- **Depends:** P-002
- **Evidence:** test output, sample redacted readiness payload.

### P-004 — Contract and schema versioning
- **Objective:** Single source of version truth (`0.1.0`) for product, contract and schemas.
- **Scope:** version module, `contract_version` in every response, schema `$id` versioning, CI
  check that schemas and code agree.
- **Acceptance:** Version mismatch fails CI; every tool response includes the version.
- **Tests/gates:** schema/contract validation job.
- **Depends:** P-002
- **Evidence:** failing-then-passing CI demonstration.

### P-005 — Manifest models (CapabilityManifest, AgentCard, ToolManifest, ExtendedToolManifest)
- **Objective:** Typed, schema-backed manifests with governance metadata.
- **Scope:** JSON schemas in `docs/schemas/`, Python models, generation from the tool registry,
  metadata fields `trust_level`, `mutation_class`, `reversible`, `idempotency_class`,
  `approval_requirement`, `attestation_status`.
- **Acceptance:** All four manifests validate; a tool missing any metadata field fails the build.
- **Tests/gates:** schema validation, completeness test over the registry.
- **Depends:** P-004
- **Evidence:** generated manifests, validation log.

### P-006 — State store and migrations
- **Objective:** SQLite state store with idempotent, forward-only migrations.
- **Scope:** schema for bindings, operations, sagas, approvals, idempotency, locks, contract and
  capability state; advisory-locked migration runner; schema version in readiness.
- **Acceptance:** Fresh DB and re-run both converge; no destructive migration; no secret columns.
- **Tests/gates:** migration idempotency test, concurrent-startup test.
- **Depends:** P-003
- **Evidence:** migration test output, schema dump.

### P-007 — FastMCP control-plane skeleton (Streamable HTTP)
- **Objective:** Serve MCP with tool registration and manifest endpoints.
- **Scope:** FastMCP app, tool registry, error taxonomy, `planner_health`, `planner_readiness`,
  `planner_agent_card`, `planner_capabilities`.
- **Acceptance:** MCP client lists tools; health/readiness behave per
  [observability.md](observability.md); readiness never requires `AUTHENTICATED`.
- **Tests/gates:** integration test against an MCP client stub.
- **Depends:** P-005, P-006
- **Evidence:** tool list output, readiness payload.

### P-008 — Structured logging with redaction
- **Objective:** JSON logs that cannot leak secrets.
- **Scope:** logging config, redaction filter (key deny-list + value patterns), per-event field
  allow-list, `operation_id` propagation.
- **Acceptance:** Deny-listed keys and secret-shaped values never appear at any level, including
  nested structures and exception messages.
- **Tests/gates:** redaction unit tests with adversarial payloads; CI log-scrape assertion.
- **Depends:** P-003
- **Evidence:** test output, sample sanitized log lines.

### P-009 — Prometheus metrics with label allow-list
- **Objective:** Low-cardinality metrics per [observability.md](observability.md).
- **Scope:** metric definitions, label allow-list enforcement, `/metrics` internal-only exposure.
- **Acceptance:** Registering a metric with a disallowed label raises at import time; cardinality
  budget documented and checked.
- **Tests/gates:** unit test for label enforcement; scrape test.
- **Depends:** P-008
- **Evidence:** scrape sample, test output.

### P-010 — Error taxonomy and typed blockers
- **Objective:** One canonical error model across control plane and worker.
- **Scope:** error codes (`BLOCKER_*`, `UI_DRIFT`, `SCHEMA_INVALID`, `TIMEOUT`, `CIRCUIT_OPEN`,
  …), mapping to MCP errors, sanitized detail fields.
- **Acceptance:** No raw exception text or DOM reaches a client response; every error carries a
  code and `operation_id`.
- **Tests/gates:** unit tests per code; response-schema validation.
- **Depends:** P-007
- **Evidence:** error catalogue test output.
---

## EPIC-02 — Browser worker & UI contract

### P-011 — FastAPI worker skeleton with typed operation envelope
- **Objective:** Internal-only worker exposing a closed operation enum.
- **Scope:** FastAPI app, `/healthz`, `/readyz`, `/operations`, `/auth/state`, `/metrics`, strict
  envelope schemas (`additionalProperties: false`), unknown-operation rejection.
- **Acceptance:** Unknown operation and schema-invalid payloads are rejected; no navigation
  primitive is exposed; worker publishes no host port.
- **Tests/gates:** schema tests, negative tests, container posture test.
- **Depends:** P-002
- **Evidence:** endpoint list, rejection test output.

### P-012 — Playwright/Chromium runtime integration
- **Objective:** Deterministic browser lifecycle inside the worker.
- **Scope:** persistent context launch, reviewed flag set (Chromium sandbox enabled, no
  `--no-sandbox`), crash detection and restart, operation deadlines, no fixed sleeps.
- **Acceptance:** Browser starts/stops cleanly; deadline exceeded ⇒ `TIMEOUT`; crash ⇒
  `BROWSER_CRASHED` and recovery.
- **Tests/gates:** L4 tests against the mock UI.
- **Depends:** P-011
- **Evidence:** run log, timing histogram sample.

### P-013 — Isolated persistent professional profile
- **Objective:** Profile isolation from personal data, enforced.
- **Scope:** dedicated volume/dir, `0700`, non-root ownership, single-writer lock, sync disabled,
  gitignore, no off-host backup, startup assertion of path and permissions.
- **Acceptance:** Startup refuses if the profile path is inside a personal directory or has wrong
  permissions; concurrent second writer is refused.
- **Tests/gates:** unit + container test.
- **Depends:** P-012
- **Evidence:** assertion test output, permission listing.

### P-014 — Centralized UIContract loader with attestation gating
- **Objective:** All selectors in one contract; unattested ⇒ refuse.
- **Scope:** `browser/selectors/` layout, fragment schema, loader, version computation,
  attestation records, `planner_ui_contract_status`.
- **Acceptance:** Using a fragment with `attestation_status = UNVERIFIED_LIVE` raises
  `UNATTESTED_FRAGMENT`; no selector exists outside the contract (CI grep gate).
- **Tests/gates:** L3 tests, repo lint forbidding inline selectors.
- **Depends:** P-011
- **Evidence:** contract status payload, lint rule output.

### P-015 — Attestation workflow and evidence handling
- **Objective:** A repeatable way to attest a fragment from live observation.
- **Scope:** operator procedure, evidence capture (DOM/screenshot hashed locally), attestation
  record writer, append-only log, structure-hash computation.
- **Acceptance:** An attestation cannot be created without an evidence hash; records are
  append-only; no artifact is committed.
- **Tests/gates:** unit tests, gitignore check.
- **Depends:** P-014
- **Evidence:** sample attestation record (hashes only).

### P-016 — UI drift detection and fail-closed handling
- **Objective:** Detect structural change before acting on it.
- **Scope:** pre-use verification of required anchors and structure hash, `BLOCKER_UI_DRIFT`,
  capability state transition to `UI_DRIFT`, circuit open, drift metric, no fallback selectors.
- **Acceptance:** Mutated mock structure ⇒ refusal, recorded drift, opened circuit; zero fallback
  attempts observed.
- **Tests/gates:** IA-05, L3/L4 drift fixtures.
- **Depends:** P-014
- **Evidence:** drift test output, metric sample.

### P-017 — Mock Planner UI harness
- **Objective:** Deterministic local UI for CI so no live tenant is ever touched.
- **Scope:** static synthetic app mirroring attested structure only, drift variant, Conditional
  Access fixture, enrolment-prompt fixture, MFA number-matching fixture.
- **Acceptance:** All browser tests run offline against the mock; no real tenant data present.
- **Tests/gates:** L4/L5 suites; CI network isolation assertion.
- **Depends:** P-012
- **Evidence:** CI job log showing no external egress.

---

## EPIC-03 — Authentication & MFA

### P-018 — Formal auth state machine
- **Objective:** Implement the eight formal states and legal transitions.
- **Scope:** state model, transition guards, reason codes, persistence of current state,
  `planner_auth_status`.
- **Acceptance:** Illegal transitions rejected; `AUTHENTICATED` only from a positive Planner-surface
  signal, never from absence of a login form.
- **Tests/gates:** exhaustive transition unit tests.
- **Depends:** P-014
- **Evidence:** transition matrix test output.

### P-019 — Interactive sign-in orchestration
- **Objective:** `planner_auth_start` / `planner_auth_resume` without credential automation.
- **Scope:** open sign-in surface in the persistent profile, poll transitions, no keystroke
  injection of credentials, operation deadlines, auth lock.
- **Acceptance:** No code path can submit a password; concurrent auth attempts are serialised.
- **Tests/gates:** code-level assertion (no credential fields), L4 test.
- **Depends:** P-018
- **Evidence:** test output, operator procedure.

### P-020 — MFA number-matching detection and sanitized event
- **Objective:** Surface the MFA number without leaking anything else.
- **Scope:** detection via attested `auth.yaml`, event with exactly `operation_id`, `service`,
  `description`, `mfa_number`, `expires_at`; strict schema.
- **Acceptance:** Adding any other field fails schema validation; no UPN/tenant/URL present;
  approval never offered in-band.
- **Tests/gates:** schema negative tests, L4 MFA fixture.
- **Depends:** P-019
- **Evidence:** sanitized event sample.

### P-021 — Conditional Access blocker
- **Objective:** Fail closed on compliant/managed-device requirements.
- **Scope:** detection, `BLOCKER_CONDITIONAL_ACCESS`, terminal `AUTH_FAILED`, circuit open, no
  retry, sanitized operator notification.
- **Acceptance:** Zero retries after the blocker; no alternate flow attempted; no bypass code
  exists.
- **Tests/gates:** IA-07, retry-count assertion.
- **Depends:** P-019
- **Evidence:** test output, notification sample.

### P-022 — Session lifecycle and expiry handling
- **Objective:** Detect and report `SESSION_EXPIRED` deterministically.
- **Scope:** periodic non-intrusive probe, expiry hint, `planner_auth_session_info` returning only
  non-secret facts, no cookie/token reads beyond presence/expiry.
- **Acceptance:** Response schema forbids session material; expiry transitions recorded.
- **Tests/gates:** schema tests, L4 expiry fixture.
- **Depends:** P-018
- **Evidence:** session-info payload sample.

### P-023 — Enrolment-prompt refusal
- **Objective:** Never enrol the personal device.
- **Scope:** detection of Company Portal/Intune/Identity Broker/device registration/certificate
  prompts, `BLOCKER_ENROLMENT_PROMPT`, terminal handling, repo gate forbidding enrolment tooling.
- **Acceptance:** Prompt is never accepted; a CI grep gate fails on enrolment automation
  references.
- **Tests/gates:** IA-08, repo gate.
- **Depends:** P-019
- **Evidence:** test output, gate configuration.

### P-024 — Account context and observed license capabilities
- **Objective:** Report only what the UI shows.
- **Scope:** `planner_account_context`, `planner_license_capabilities`, ambiguity ⇒
  `BLOCKER_AMBIGUOUS_SESSION`, no inference from Graph or marketing.
- **Acceptance:** No capability is reported as present without a UI observation; multiple
  candidate accounts ⇒ blocker, never a pick.
- **Tests/gates:** L4 ambiguity fixture, unit tests.
- **Depends:** P-018
- **Evidence:** payload sample, capability rows updated.
---

## EPIC-04 — Read model

### P-025 — Plan/project list read
- **Objective:** `planner_plan_list` returning typed, schema-valid plans.
- **Scope:** attested `plan_list` fragment, extraction to typed model, stable `external_id`
  capture, pagination/virtualised-list handling, empty-state handling.
- **Acceptance:** Deterministic output across two consecutive reads; unattested fragment ⇒ refuse.
- **Tests/gates:** IA-03, L4.
- **Depends:** P-018
- **Evidence:** result hash, schema validation log.

### P-026 — Plan/project detail read
- **Objective:** `planner_plan_get` by `external_id`.
- **Scope:** plan metadata, buckets summary, counts, Premium indicators observed.
- **Acceptance:** Unknown `external_id` ⇒ typed not-found, never a guess; schema-valid output.
- **Tests/gates:** L4, schema tests.
- **Depends:** P-025
- **Evidence:** payload sample (synthetic), result hash.

### P-027 — Task list and task detail reads
- **Objective:** `planner_task_list`, `planner_task_get` with typed fields.
- **Scope:** grid extraction, field normalisation (dates RFC3339, effort with unit, progress),
  hierarchy parent/child capture, stable task `external_id`.
- **Acceptance:** Normalisation failures surface as typed errors rather than silent nulls.
- **Tests/gates:** IA-03, normalisation unit tests.
- **Depends:** P-026
- **Evidence:** schema-valid payload, test output.

### P-028 — Bucket read model
- **Objective:** Read buckets and their ordering.
- **Scope:** bucket list per plan, order index, task membership mapping.
- **Acceptance:** Ordering is stable and explicit; membership consistent with task reads.
- **Tests/gates:** L4, consistency test.
- **Depends:** P-027
- **Evidence:** payload sample.

### P-029 — Dependency edge read model
- **Objective:** Read dependency edges as `(predecessor, successor, type, lag)`.
- **Scope:** FS/SS/SF/FF typing, lag units, dangling-edge detection.
- **Acceptance:** Unknown edge type ⇒ typed error, never coerced to FS.
- **Tests/gates:** L4, unit tests for edge parsing.
- **Depends:** P-027
- **Evidence:** edge list sample.

### P-030 — Project snapshot with stable hash
- **Objective:** `planner_project_snapshot` composite read.
- **Scope:** plan + buckets + tasks + edges in one consistent pass, normalisation, `snapshot_hash`,
  partial-capability labelling.
- **Acceptance:** Two identical reads produce an identical hash; any degraded capability is
  labelled, not omitted.
- **Tests/gates:** IA-04.
- **Depends:** P-027, P-028, P-029
- **Evidence:** two-run hash equality log.

---

## EPIC-05 — Mutations

### P-031 — Mutation framework: policy, locks, read-back, sagas
- **Objective:** The single path every mutation must take.
- **Scope:** policy gate, approval check, idempotency lookup, typed exclusive lock, apply,
  read-back, checkpoint, compensation, circuit breaker, retry policy.
- **Acceptance:** No mutating code path can bypass the framework (enforced by design + test);
  retry only after read-back; `READ_BACK_OK` is the sole success terminal.
- **Tests/gates:** IA-09..IA-13.
- **Depends:** P-030
- **Evidence:** framework test suite output.

### P-032 — Task create/update/delete
- **Objective:** First real mutations.
- **Scope:** create (KEYED_IDEMPOTENT via `source_id`), update fields (NATURAL_IDEMPOTENT), delete
  (DESTRUCTIVE), each with a read-back strategy.
- **Acceptance:** Duplicate create suppressed by binding; delete verified absent on re-read.
- **Tests/gates:** L4/L5 with mock; approval tests.
- **Depends:** P-031
- **Evidence:** read-back logs, capability row → `MUTATION_ATTESTED` (live only).

### P-033 — Bucket mutations
- **Objective:** Create, rename, reorder, delete buckets.
- **Scope:** ordering semantics, membership preservation on delete (explicit policy), read-back of
  the bucket set.
- **Acceptance:** Delete with non-empty bucket requires explicit approval and states task
  disposition.
- **Tests/gates:** L4, policy tests.
- **Depends:** P-031
- **Evidence:** before/after bucket sets.

### P-034 — Assignment mutations
- **Objective:** Assign/unassign people to tasks.
- **Scope:** person resolution (exact match only), ambiguity blocker, read-back of assignee set.
- **Acceptance:** Ambiguous person ⇒ `BLOCKER_AMBIGUOUS_IDENTITY`, never a best guess.
- **Tests/gates:** L4 ambiguity fixture.
- **Depends:** P-031
- **Evidence:** assignment diff.

### P-035 — Plan lifecycle mutations
- **Objective:** Create/archive/delete plans.
- **Scope:** DESTRUCTIVE classification for delete, explicit policy rule requirement, binding
  creation on create, read-back.
- **Acceptance:** Delete without an explicit rule ⇒ `DENY`; create binds `source_id ⇄ external_id`.
- **Tests/gates:** policy default-deny tests.
- **Depends:** P-031
- **Evidence:** policy decision log.

### P-036 — Bulk mutation safety
- **Objective:** Prevent large blast radius by accident.
- **Scope:** batch size limits, per-batch approval, dry-run requirement above a threshold,
  progress checkpoints, abort with compensation.
- **Acceptance:** Exceeding the threshold without a dry-run ⇒ `DENY`; partial failure reports exact
  affected ids.
- **Tests/gates:** L1/L5 tests.
- **Depends:** P-031
- **Evidence:** dry-run output, abort log.

---

## EPIC-06 — Scheduling & PM semantics

### P-037 — Duration, effort and units
- **Objective:** Read/write effort and duration with explicit units.
- **Scope:** unit normalisation, ambiguity refusal, read-back with unit verification.
- **Acceptance:** Unit-ambiguous input ⇒ `DENY`; read-back compares normalized values.
- **Tests/gates:** unit tests, L4.
- **Depends:** P-031
- **Evidence:** conversion test matrix.

### P-038 — WBS hierarchy operations
- **Objective:** Summary tasks, indent/outdent, reparenting.
- **Scope:** hierarchy invariants, ordering, read-back of parent/child edges, cycle prevention.
- **Acceptance:** Invalid hierarchy operation refused before apply.
- **Tests/gates:** L4, invariant tests.
- **Depends:** P-037
- **Evidence:** tree before/after.

### P-039 — Dependency mutations with validation
- **Objective:** Add/remove FS/SS/SF/FF edges safely.
- **Scope:** pre-apply cycle detection, lag handling, `planner_dependency_validate`, read-back on
  both endpoints.
- **Acceptance:** Any cycle-creating edge is refused **before** touching the UI.
- **Tests/gates:** graph unit tests, L4.
- **Depends:** P-038
- **Evidence:** validation report sample.

### P-040 — Milestones
- **Objective:** Mark/unmark milestones and set their dates.
- **Scope:** milestone flag semantics, date coupling, read-back.
- **Acceptance:** Flag and date verified together on read-back.
- **Tests/gates:** L4.
- **Depends:** P-037
- **Evidence:** milestone diff.

### P-041 — Scheduling and timeline reads
- **Objective:** Dates that respect Planner's own recalculation.
- **Scope:** set start/finish, wait for recalculation to settle, timeline/Gantt read, no local
  schedule computation.
- **Acceptance:** Read-back occurs only after a settled state; non-settling schedule ⇒ fail closed.
- **Tests/gates:** L4 settle fixture.
- **Depends:** P-039
- **Evidence:** settle timing log.

### P-042 — Critical path read
- **Objective:** Report Planner's critical path, not a local reimplementation.
- **Scope:** read the product's indicator; if absent, report unavailable.
- **Acceptance:** No locally computed critical path is presented as Planner's.
- **Tests/gates:** L4.
- **Depends:** P-041
- **Evidence:** payload sample.

### P-043 — People and workload
- **Objective:** Read the workload/people view.
- **Scope:** aggregated capacity/assignment reads, privacy-minimised output.
- **Acceptance:** No free-text personal data beyond names required by the caller; nothing logged.
- **Tests/gates:** telemetry hygiene test.
- **Depends:** P-034
- **Evidence:** aggregated payload.

### P-044 — Goals
- **Objective:** Read and link goals where licensed.
- **Scope:** goal list, link/unlink to plan/task, `UNSUPPORTED_TENANT` when absent.
- **Acceptance:** Absence handled as an observed fact, not an error to retry.
- **Tests/gates:** L4.
- **Depends:** P-031
- **Evidence:** capability row update.

### P-045 — Sprints and backlog
- **Objective:** Sprint lifecycle and membership.
- **Scope:** list/create sprints, assign tasks, backlog read, read-back of membership.
- **Acceptance:** Membership verified per task after apply.
- **Tests/gates:** L4.
- **Depends:** P-031
- **Evidence:** membership diff.
---

## EPIC-07 — Reconciliation & blueprints

### P-046 — Custom fields
- **Objective:** Read/define/set custom fields with typed values.
- **Scope:** field discovery, type mapping, unknown type refusal, read-back with type check.
- **Acceptance:** Unknown field type ⇒ `DENY`, never a string coercion.
- **Tests/gates:** unit + L4.
- **Depends:** P-031
- **Evidence:** field type matrix.

### P-047 — Conditional coloring / formatting rules
- **Objective:** Read and set formatting rule sets.
- **Scope:** rule model, ordering, read-back of the rule set as a whole.
- **Acceptance:** Partial rule application is impossible; the set is applied or refused.
- **Tests/gates:** L4.
- **Depends:** P-046
- **Evidence:** rule-set diff.

### P-048 — Calendar and working time
- **Objective:** Read/set project calendar configuration.
- **Scope:** working days/hours, exceptions, approval requirement (affects all dates), read-back.
- **Acceptance:** Always `GOVERNED_WRITE` with approval; schedule impact stated in the dry-run.
- **Tests/gates:** policy tests, L4.
- **Depends:** P-041
- **Evidence:** approval record + diff.

### P-049 — Binding registry (`source_id ⇄ external_id`)
- **Objective:** Stable identity mapping with adoption rules.
- **Scope:** binding CRUD, unique-match adoption, `AMBIGUOUS`/`ORPHANED` states, evidence hash,
  last-verified tracking.
- **Acceptance:** Ambiguous match never creates; orphaned binding never silently recreates.
- **Tests/gates:** unit tests for all match cases.
- **Depends:** P-006
- **Evidence:** binding table dump (synthetic).

### P-050 — Desired-state reconciliation engine
- **Objective:** Diff → ordered plan → apply → read-back → converge/compensate.
- **Scope:** typed diff per entity kind, topological ordering, strict-mode removals as
  DESTRUCTIVE, snapshot pinning, resume from checkpoint, indeterminate handling.
- **Acceptance:** Crash mid-run resumes without replaying applied steps; snapshot change ⇒
  `SNAPSHOT_STALE`.
- **Tests/gates:** IA-12, IA-13.
- **Depends:** P-031, P-049
- **Evidence:** resume log, diff report.

### P-051 — Blueprint format and validation
- **Objective:** Declarative project blueprint as the reconciliation input.
- **Scope:** schema (plans, buckets, tasks, hierarchy, edges, dates, effort, fields, assignments),
  `source_id` requirements, `planner_blueprint_validate`.
- **Acceptance:** Invalid blueprint rejected with precise paths; no partial parse.
- **Tests/gates:** schema tests with adversarial fixtures.
- **Depends:** P-050
- **Evidence:** validation output.

### P-052 — Dry-run planning and import safety
- **Objective:** Never import blind.
- **Scope:** `planner_blueprint_plan` producing the ordered operation list with classes and
  predicted diffs; import requires a successful dry-run referenced by hash.
- **Acceptance:** Apply without a matching dry-run hash ⇒ `DENY`.
- **Tests/gates:** L1/L5.
- **Depends:** P-051
- **Evidence:** dry-run report + apply linkage.

### P-053 — Reconciliation status and resume tools
- **Objective:** Operate long-running runs.
- **Scope:** `planner_reconcile_status`, `planner_reconcile_resume`, per-step visibility, affected
  id listing for indeterminate steps.
- **Acceptance:** Indeterminate ids are always enumerated; no run can be resumed while a lock lease
  is expired without re-reading.
- **Tests/gates:** L5.
- **Depends:** P-050
- **Evidence:** status payload.

---

## EPIC-08 — Reporting & portfolio

### P-054 — Portfolio and roadmap reads
- **Objective:** Read portfolio membership and roadmap structure.
- **Scope:** portfolio list/get, plan membership, `UNSUPPORTED_TENANT` handling.
- **Acceptance:** Membership consistent with plan reads; unavailability reported as observed.
- **Tests/gates:** L4.
- **Depends:** P-030
- **Evidence:** payload sample.

### P-055 — Snapshot history store
- **Objective:** Retain snapshots for trend reporting.
- **Scope:** snapshot table, retention policy, hash-only long-term retention, configurable TTL for
  payloads.
- **Acceptance:** Retention enforced; no unbounded tenant-data growth.
- **Tests/gates:** retention unit tests.
- **Depends:** P-030
- **Evidence:** retention test output.

### P-056 — Status and variance reports
- **Objective:** Plan status and schedule variance projections.
- **Scope:** typed report payloads, baseline comparison, `provisional` labelling when a
  contributing capability is below `READ_ATTESTED`.
- **Acceptance:** Any provisional section is labelled; freshness always present.
- **Tests/gates:** unit tests over fixtures.
- **Depends:** P-055
- **Evidence:** report sample (synthetic).

### P-057 — Portfolio rollup reporting
- **Objective:** Aggregate plan health across a portfolio.
- **Scope:** rollup aggregation, missing-plan handling, restructure classified DESTRUCTIVE.
- **Acceptance:** Missing/blocked plans are listed, never dropped.
- **Tests/gates:** unit tests.
- **Depends:** P-054, P-056
- **Evidence:** rollup sample.

### P-058 — Sharing and permissions (default-deny)
- **Objective:** Read membership; mutate only under an explicit rule.
- **Scope:** member/role read, DESTRUCTIVE classification for changes, approval, read-back.
- **Acceptance:** No sharing mutation is possible without an explicit policy rule and approval.
- **Tests/gates:** policy default-deny tests.
- **Depends:** P-035
- **Evidence:** policy decision log.

### P-059 — Export and external reporting surfaces
- **Objective:** Controlled export of project data.
- **Scope:** export formats, local write with restrictive permissions, no commit, no telemetry of
  content, Power BI/reporting surface read where observed.
- **Acceptance:** Exports never leave the host through this system; paths are reported, content is
  not logged.
- **Tests/gates:** telemetry hygiene test.
- **Depends:** P-056
- **Evidence:** export path + hash.

### P-060 — Governance reporting
- **Objective:** Auditable view of decisions and blockers.
- **Scope:** report over policy decisions, approvals, blockers, drift events for a time window.
- **Acceptance:** Every governed mutation in the window is present with its decision and approval
  id.
- **Tests/gates:** unit tests over the state DB.
- **Depends:** P-050
- **Evidence:** governance report sample.
---

## EPIC-09 — Security, governance & observability

### P-061 — Policy engine with default-deny
- **Objective:** Deterministic `ALLOW`/`DENY`/`REQUIRE_APPROVAL` decisions.
- **Scope:** rule model, evaluation order, default-deny for GOVERNED_WRITE/DESTRUCTIVE, decision
  logging with rule id, `planner_policy_explain`.
- **Acceptance:** Missing rule ⇒ `DENY`; every decision is explainable and recorded.
- **Tests/gates:** IA-09, unit matrix.
- **Depends:** P-010
- **Evidence:** decision matrix output.

### P-062 — Approval store: persistent, single-use, non-replayable
- **Objective:** Approvals that cannot be reused or forged.
- **Scope:** approval lifecycle, fingerprint binding, expiry, consumption, revoke, callback
  verification.
- **Acceptance:** Replay rejected; changed arguments invalidate the approval; expired approval
  refused.
- **Tests/gates:** IA-10.
- **Depends:** P-061
- **Evidence:** replay test output.

### P-063 — Secret-handling and telemetry hygiene gates
- **Objective:** Make leakage a build failure.
- **Scope:** secret scanning in CI, redaction tests with adversarial payloads, log/metric scrape
  assertions, gitignore of profile/state/evidence/.env, prohibition of credential-shaped config.
- **Acceptance:** Any deny-listed pattern in logs, metrics or the repo fails CI.
- **Tests/gates:** IA-14, secret-scan job.
- **Depends:** P-008, P-009
- **Evidence:** CI job logs.

### P-064 — Container hardening and compose posture
- **Objective:** Enforce the runtime posture in
  [deployment.md](deployment.md).
- **Scope:** non-root, read-only FS, `cap_drop ALL`, `no-new-privileges`, tmpfs, internal network,
  no docker socket, no host home mount, resource limits, healthchecks.
- **Acceptance:** Posture asserted by an automated check; worker unreachable from the host network.
- **Tests/gates:** IA-15.
- **Depends:** P-011
- **Evidence:** posture check output.

### P-065 — Supply chain: SBOM, vulnerability and pinning gates
- **Objective:** Known-good dependencies and images.
- **Scope:** CycloneDX SBOM generation + validation, dependency vulnerability scan, Trivy with
  CRITICAL/HIGH failure, digest-pinned base images with a CI pin check.
- **Acceptance:** Unpinned base image or CRITICAL/HIGH finding fails the build.
- **Tests/gates:** IA-16.
- **Depends:** P-002
- **Evidence:** SBOM artifact, scan reports.

### P-066 — Circuit breakers and retry policy
- **Objective:** Bounded failure behaviour.
- **Scope:** per-family breakers, half-open probes using reads only, retry budgets with jitter,
  auth excluded from auto-retry.
- **Acceptance:** Breaker opens on drift/CA blockers; no auth retry storm is possible.
- **Tests/gates:** unit + L5.
- **Depends:** P-031
- **Evidence:** breaker state metrics.

### P-067 — Audit trail completeness
- **Objective:** Every governed action is reconstructable.
- **Scope:** `operation_id` correlation across control plane and worker, persisted decision,
  approval, checkpoints and read-back outcome, retention policy.
- **Acceptance:** For any governed operation, the full chain can be reconstructed from the state DB
  without consulting logs.
- **Tests/gates:** audit reconstruction test.
- **Depends:** P-062
- **Evidence:** reconstruction output.

---

## EPIC-10 — Acceptance & release

### P-068 — CI pipeline complete
- **Objective:** All gates wired and enforced on PRs.
- **Scope:** compile, ruff, mypy, pytest, schema/contract validation, secret scan, dependency
  scan, container build, Trivy, SBOM, isolated acceptance; branch protection required checks.
- **Acceptance:** A PR cannot merge with any gate red; CI performs no live-tenant call.
- **Tests/gates:** the pipeline itself.
- **Depends:** P-065
- **Evidence:** CI run URL, required-checks configuration.

### P-069 — Isolated acceptance suite (IA-01..IA-16)
- **Objective:** Automated end-to-end proof against the mock UI.
- **Scope:** compose stack, fixtures (drift, CA, enrolment, MFA), assertions, artifacts.
- **Acceptance:** All IA checks pass in CI; failures block merge.
- **Tests/gates:** IA suite.
- **Depends:** P-031, P-017
- **Evidence:** acceptance report artifact.

### P-070 — Live read-only acceptance procedure
- **Objective:** A repeatable operator procedure for LA-01..LA-11.
- **Scope:** documented steps, evidence capture rules (hashes only), sanitization checklist,
  results recorded in the capability matrix and attestation log.
- **Acceptance:** Procedure executable without any mutation and without storing tenant content.
- **Tests/gates:** manual, reviewed.
- **Depends:** P-069
- **Evidence:** completed LA record or a recorded blocker.

### P-071 — Traceability matrix closure
- **Objective:** Requirements ⇄ ADR/architecture ⇄ backlog ⇄ tests/evidence fully mapped.
- **Scope:** maintain [traceability.md](traceability.md); CI check that every `SEC-*` and every
  hard requirement has at least one backlog key and one test id.
- **Acceptance:** No orphan requirement, no orphan test id.
- **Tests/gates:** traceability lint.
- **Depends:** P-069
- **Evidence:** lint output.

### P-072 — Documentation completeness gate
- **Objective:** Docs stay truthful as code lands.
- **Scope:** check that every implemented tool appears in the tool catalog with matching metadata,
  and that no capability row claims a state without an evidence hash.
- **Acceptance:** Mismatch between registry and docs fails CI.
- **Tests/gates:** docs consistency job.
- **Depends:** P-005
- **Evidence:** job output.

### P-073 — Release process and gates
- **Objective:** Reproducible, gated releases.
- **Scope:** [release-process.md](release-process.md) implementation: version bump, changelog,
  SBOM publication, image digests, tag, post-merge verification.
- **Acceptance:** A release cannot be cut with any gate red or with an unattested capability
  claimed as supported.
- **Tests/gates:** release workflow dry-run.
- **Depends:** P-071
- **Evidence:** release artifacts list.

### P-074 — 0.1.0 release
- **Objective:** Ship the read-only contract.
- **Scope:** tag `v0.1.0`, published SBOM, pinned digests, capability matrix reflecting only
  attested states, known blockers documented.
- **Acceptance:** Definition of Done met for every included item; no `UNVERIFIED_LIVE` row
  presented as supported.
- **Tests/gates:** all gates green.
- **Depends:** P-073
- **Evidence:** release URL, CI run, acceptance reports.

---

## Dependency summary

| Key | Depends on |
| --- | --- |
| P-001 | — |
| P-002 | P-001 |
| P-003 | P-002 |
| P-004 | P-002 |
| P-005 | P-004 |
| P-006 | P-003 |
| P-007 | P-005, P-006 |
| P-008 | P-003 |
| P-009 | P-008 |
| P-010 | P-007 |
| P-011 | P-002 |
| P-012 | P-011 |
| P-013 | P-012 |
| P-014 | P-011 |
| P-015 | P-014 |
| P-016 | P-014 |
| P-017 | P-012 |
| P-018 | P-014 |
| P-019 | P-018 |
| P-020 | P-019 |
| P-021 | P-019 |
| P-022 | P-018 |
| P-023 | P-019 |
| P-024 | P-018 |
| P-025 | P-018 |
| P-026 | P-025 |
| P-027 | P-026 |
| P-028 | P-027 |
| P-029 | P-027 |
| P-030 | P-027, P-028, P-029 |
| P-031 | P-030 |
| P-032 | P-031 |
| P-033 | P-031 |
| P-034 | P-031 |
| P-035 | P-031 |
| P-036 | P-031 |
| P-037 | P-031 |
| P-038 | P-037 |
| P-039 | P-038 |
| P-040 | P-037 |
| P-041 | P-039 |
| P-042 | P-041 |
| P-043 | P-034 |
| P-044 | P-031 |
| P-045 | P-031 |
| P-046 | P-031 |
| P-047 | P-046 |
| P-048 | P-041 |
| P-049 | P-006 |
| P-050 | P-031, P-049 |
| P-051 | P-050 |
| P-052 | P-051 |
| P-053 | P-050 |
| P-054 | P-030 |
| P-055 | P-030 |
| P-056 | P-055 |
| P-057 | P-054, P-056 |
| P-058 | P-035 |
| P-059 | P-056 |
| P-060 | P-050 |
| P-061 | P-010 |
| P-062 | P-061 |
| P-063 | P-008, P-009 |
| P-064 | P-011 |
| P-065 | P-002 |
| P-066 | P-031 |
| P-067 | P-062 |
| P-068 | P-065 |
| P-069 | P-031, P-017 |
| P-070 | P-069 |
| P-071 | P-069 |
| P-072 | P-005 |
| P-073 | P-071 |
| P-074 | P-073 |
