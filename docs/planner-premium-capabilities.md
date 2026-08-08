# Planner Premium capability matrix

**Microsoft Graph availability does not determine support.** Graph is contextual information
only and is never a functional gate (ADR-006). Support here is decided by *observed browser
evidence* in the tenant UI.

Nothing in this matrix is live-attested yet. Every row starts at `UNVERIFIED_LIVE`. No tenant
fact, license fact or selector below is asserted as observed — the columns are the contract for
recording evidence, not a claim that evidence exists.

## Capability states

| State | Meaning | Entry requirement |
| --- | --- | --- |
| `UNVERIFIED_LIVE` | Listed for discovery; nothing observed. | default |
| `DISCOVERED` | Surface seen in the tenant UI by an operator. | dated observation note |
| `UI_ATTESTED` | Selectors recorded in the UIContract with attestation evidence. | contract fragment + evidence hash |
| `READ_ATTESTED` | Deterministic typed read demonstrated and schema-valid. | passing read evidence |
| `MUTATION_ATTESTED` | Mutation demonstrated **with successful read-back**. | apply + read-back evidence |
| `SUPPORTED` | Exposed through a semantic tool with policy, idempotency and drift handling. | attested + tool + tests + policy rule |
| `UI_DRIFT` | Previously attested surface no longer matches; operations fail closed. | drift detection event |
| `BLOCKED_CONDITIONAL_ACCESS` | Unreachable due to device-compliance policy. | blocker event |
| `UNSUPPORTED_TENANT` | Not present/licensed in this tenant. | dated observation note |

Transitions are forward-only except `UI_DRIFT` (→ re-attestation) and blocker states. A state may
never be advanced by documentation alone (see [governance.md](governance.md)).

## Column definitions

- **Capability / domain** — semantic project capability, not a UI widget.
- **Tenant / license observed** — what was actually seen (`unverified` until an operator records
  it). Never inferred from marketing material.
- **UI observed** — the Premium surface where the capability lives, once seen.
- **UIContract / selector attestation** — contract fragment id + attestation status.
- **READ validated** — a typed, schema-valid read has been produced.
- **MUTATION validated** — apply + read-back demonstrated.
- **Support level** — state from the table above.
- **Policy / mutation class** — required class for the governing operation.
- **Read-back strategy** — how the effect is verified after a write.
- **Drift / failure behavior** — always fail closed; column records the specific typed error.
- **Notes / evidence** — evidence handle or open question.

## Matrix

Legend for evidence columns: `no` = not demonstrated, `n/a` = not applicable at this level.

| Capability / domain | Tenant / license observed | UI observed | UIContract / attestation | READ validated | MUTATION validated | Support level | Policy / mutation class | Read-back strategy | Drift / failure behavior | Notes / evidence |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Plans / projects — list | unverified | unverified | none | no | n/a | UNVERIFIED_LIVE | READ | n/a | `UI_DRIFT` fail closed | entry point for all reads; P-025 |
| Plan / project — detail read | unverified | unverified | none | no | n/a | UNVERIFIED_LIVE | READ | n/a | `UI_DRIFT` | needs stable `external_id`; P-026 |
| Plan / project — create | unverified | unverified | none | no | no | UNVERIFIED_LIVE | GOVERNED_WRITE | re-read by name+owner, bind `external_id` | fail closed, no retry pre-read-back | P-031 |
| Plan / project — delete | unverified | unverified | none | no | no | UNVERIFIED_LIVE | DESTRUCTIVE | re-read must return absent | explicit rule required | P-035 |
| WBS — summary tasks / hierarchy | unverified | unverified | none | no | no | UNVERIFIED_LIVE | GOVERNED_WRITE | re-read parent/child edges | fail closed | grid view; P-027, P-038 |
| Subtasks / checklist | unverified | unverified | none | no | no | UNVERIFIED_LIVE | SAFE_WRITE | re-read task detail | fail closed | P-032 |
| Buckets | unverified | unverified | none | no | no | UNVERIFIED_LIVE | SAFE_WRITE | re-read bucket set | fail closed | P-028, P-033 |
| Assignments (people on tasks) | unverified | unverified | none | no | no | UNVERIFIED_LIVE | GOVERNED_WRITE | re-read assignee set on task | ambiguous person ⇒ `BLOCKER_AMBIGUOUS_IDENTITY` | P-034, P-043 |
| Dependencies FS / SS / SF / FF | unverified | unverified | none | no | no | UNVERIFIED_LIVE | GOVERNED_WRITE | re-read edge type + lag on both ends | cycle ⇒ deny before apply | P-029, P-039 |
| Milestones | unverified | unverified | none | no | no | UNVERIFIED_LIVE | GOVERNED_WRITE | re-read flag + date | fail closed | P-040 |
| Duration / effort | unverified | unverified | none | no | no | UNVERIFIED_LIVE | GOVERNED_WRITE | re-read numeric fields with unit | unit ambiguity ⇒ deny | P-037 |
| Scheduling (start/finish, calendar-driven) | unverified | unverified | none | no | no | UNVERIFIED_LIVE | GOVERNED_WRITE | re-read computed dates after recalculation settles | non-settling schedule ⇒ fail closed | P-037, P-041 |
| Timeline / Gantt view | unverified | unverified | none | no | n/a | UNVERIFIED_LIVE | READ | n/a | `UI_DRIFT` | read-only rendering surface; P-041 |
| Critical path | unverified | unverified | none | no | n/a | UNVERIFIED_LIVE | READ | n/a | fail closed if indicator absent | derived; must be read, not computed locally; P-042 |
| People / workload view | unverified | unverified | none | no | n/a | UNVERIFIED_LIVE | READ | n/a | `UI_DRIFT` | P-043 |
| Goals (OKR linkage) | unverified | unverified | none | no | no | UNVERIFIED_LIVE | GOVERNED_WRITE | re-read goal linkage on task/plan | licensing may differ ⇒ `UNSUPPORTED_TENANT` | P-044 |
| Sprints / backlog | unverified | unverified | none | no | no | UNVERIFIED_LIVE | GOVERNED_WRITE | re-read sprint membership | fail closed | P-045 |
| Custom fields | unverified | unverified | none | no | no | UNVERIFIED_LIVE | GOVERNED_WRITE | re-read field value + type | unknown field type ⇒ deny | P-046 |
| Conditional coloring / formatting rules | unverified | unverified | none | no | no | UNVERIFIED_LIVE | GOVERNED_WRITE | re-read rule set | fail closed | P-047 |
| Calendar / working time | unverified | unverified | none | no | no | UNVERIFIED_LIVE | GOVERNED_WRITE | re-read calendar config | affects all dates ⇒ approval | P-048 |
| Task history / conversations | unverified | unverified | none | no | n/a | UNVERIFIED_LIVE | READ | n/a | `UI_DRIFT` | read-only; privacy-sensitive, minimise extraction; P-030 |
| Portfolios / roadmaps | unverified | unverified | none | no | no | UNVERIFIED_LIVE | GOVERNED_WRITE | re-read portfolio membership | restructure ⇒ DESTRUCTIVE | P-054, P-057 |
| Sharing / permissions | unverified | unverified | none | no | no | UNVERIFIED_LIVE | DESTRUCTIVE | re-read member/role list | explicit rule required; default deny | P-058 |
| Import / export | unverified | unverified | none | no | no | UNVERIFIED_LIVE | DESTRUCTIVE | full re-read diff vs blueprint | overwrite semantics ⇒ approval + dry-run first | P-051, P-052 |
| Reporting / Power BI surface | unverified | unverified | none | no | n/a | UNVERIFIED_LIVE | READ | n/a | fail closed | may be out-of-product; P-059 |
| Account / license context | unverified | unverified | none | no | n/a | UNVERIFIED_LIVE | READ | n/a | ambiguity ⇒ `BLOCKER_AMBIGUOUS_SESSION` | P-024; never asserts a license not observed |

## Rules for updating this file

1. Change a state only together with an evidence handle recorded in the UI contract attestation
   log.
2. Never write a selector into this file; selectors live only in `browser/selectors` UIContract.
3. Never record a tenant, license or capability fact that was not directly observed.
4. `SUPPORTED` additionally requires: semantic tool implemented, policy rule present, tests
   against the mock UI, drift handling, and (for writes) a demonstrated read-back.

---

# Expanded specification — evidence contract, lifecycle and per-capability detail

The section above is the normative matrix and MUST NOT be silently altered. The material below
expands the contract with the machinery that makes each row advance, the rules that keep it
honest, and the implementation detail a tool author needs. Requirement IDs `CAP-xxx` are stable
and never reused.

## CAP-001 — Baseline posture: nothing is asserted as observed

- **CAP-001.** Every capability row SHALL start at `UNVERIFIED_LIVE`. The matrix is a discovery
  and recording contract, not a description of live tenant state.
- **CAP-002.** No tenant fact, license fact, selector, or `external_id` in this file SHALL be
  recorded unless an operator directly observed it in the tenant UI. Marketing material, Graph
  metadata, release notes, and model-generated guesses are explicitly out of scope as evidence
  (`UI-002`, `UI-003`).
- **CAP-003.** The `Tenant / license observed` column SHALL read `unverified` until an operator
  records a dated note; the column is never inferred from the capability's theoretical existence
  in the Planner Premium SKU.
- **CAP-004.** A capability MAY legitimately remain `UNVERIFIED_LIVE` for the entire supported
  life of the product. Non-attestation is not a defect; it is the safe default.

## CAP-005 — Graph is contextual information, never a gate (ADR-006)

- **CAP-005.** Microsoft Graph SHALL be used only to *contextualise* (`planner_account_context`,
  `planner_license_capabilities`) what the browser worker has or will observe. Graph responses
  SHALL NOT be used to decide whether a capability is supported, reachable, or safe to mutate.
- **CAP-006.** When Graph and observed browser evidence disagree, the browser evidence wins and
  the discrepancy is recorded as a drift note; the system SHALL NOT silently prefer Graph.
- **CAP-007.** `planner_license_capabilities` SHALL report only capabilities *observed* in the UI;
  a Premium license present in Graph but absent in the UI yields `UNSUPPORTED_TENANT` for that
  row, never a false positive.
- **CAP-008.** There SHALL be no code path in the control plane or worker that reads a Graph
  capability flag and uses it to enable, disable, or gate a mutation. Graph access is optional and
  failure of Graph lookups SHALL NOT block browser-driven reads or writes.

## CAP-009 — Support is decided by observed browser evidence

- **CAP-009.** The `Support level` of a row SHALL change only on the basis of recorded browser
  evidence (UIContract fragment + attestation hash, passing read evidence, and — for mutating
  capabilities — apply + read-back evidence).
- **CAP-010.** The browser worker is the system of record for "does this work here". The control
  plane derives capability state from `ui_contract_state` and `capability_state` tables
  (see [state-model.md](state-model.md)) and from runtime probes, never from a static assumption.

## CAP-010..CAP-013 — State lifecycle evidence requirements

The lifecycle states in the matrix are the same values used by the UIContract attestation
lifecycle (`UI-041`). The evidence required to enter each is:

| Target state | Minimum evidence to advance | Governing rule |
| --- | --- | --- |
| `DISCOVERED` | A dated operator note that the surface/element exists in the tenant UI. | `UI-041` |
| `UI_ATTESTED` | A locator resolved uniquely in a recorded read-only observation, with expected role/text/structure (`UI-011`, `UI-020`). | `UI-002`, `GOV-043` |
| `READ_ATTESTED` | A semantic read returned schema-valid data and its read-back probe confirmed it. | `UI-060`, `SEC-006` |
| `MUTATION_ATTESTED` | A governed mutation took effect and was confirmed by read-back, with compensation demonstrated. | ADR-003, `UI-063` |
| `SUPPORTED` | `MUTATION_ATTESTED` (or `READ_ATTESTED` for read-only) **plus** a governance decision to publish the tool (`GOV-010`). | `GOV-010`, `GOV-011` |
| `UI_DRIFT` | Any observation contradicting the attested expectation; terminal until re-attestation. | `UI-043`, `GOV-012` |

- **CAP-011.** State advancement SHALL be forward-only. Skipping a state (e.g. `UNVERIFIED_LIVE`
  → `SUPPORTED`) is prohibited (`GOV-011`).
- **CAP-012.** `UI_DRIFT` is terminal and fail-closed: while a row is in `UI_DRIFT`, every
  operation depending on it is refused with `UI_DRIFT`; the only exit is re-attestation from
  `DISCOVERED` upward with fresh evidence under a reviewed change (`UI-043`).
- **CAP-013.** Attestation expires on contract bump, observed UI surface version change, locale
  change affecting text anchors, a drift detection, or the configured maximum attestation age
  (`GOV-044`, `GOV-045`). Expiry returns the row to `UNVERIFIED_LIVE`, not to a lower attested
  state.

## CAP-014 — Capability requirement ID index

The `UIContract` `capability_key` for each row is the stable key below; `UI-011` requires it to
match a `CAP-xxx` row. This index is the authoritative mapping.

| `capability_key` | Row | Mutation class | Default decision | Reversible |
| --- | --- | --- | --- | --- |
| `CAP-001` | Plans / projects — list | `READ` | `ALLOW` | n/a |
| `CAP-002` | Plan / project — detail read | `READ` | `ALLOW` | n/a |
| `CAP-003` | Plan / project — create | `GOVERNED_WRITE` | `REQUIRE_APPROVAL` | usually |
| `CAP-004` | Plan / project — delete | `DESTRUCTIVE` | `REQUIRE_APPROVAL` | no |
| `CAP-005` | WBS — summary tasks / hierarchy | `GOVERNED_WRITE` | `REQUIRE_APPROVAL` | usually |
| `CAP-006` | Subtasks / checklist | `SAFE_WRITE` | `ALLOW` under rule | yes |
| `CAP-007` | Buckets | `SAFE_WRITE` | `ALLOW` under rule | yes |
| `CAP-008` | Assignments | `GOVERNED_WRITE` | `REQUIRE_APPROVAL` | usually |
| `CAP-009` | Dependencies FS/SS/SF/FF | `GOVERNED_WRITE` | `REQUIRE_APPROVAL` | usually |
| `CAP-010` | Milestones | `GOVERNED_WRITE` | `REQUIRE_APPROVAL` | usually |
| `CAP-011` | Duration / effort | `GOVERNED_WRITE` | `REQUIRE_APPROVAL` | usually |
| `CAP-012` | Scheduling | `GOVERNED_WRITE` | `REQUIRE_APPROVAL` | usually |
| `CAP-013` | Timeline / Gantt view | `READ` | `ALLOW` | n/a |
| `CAP-014` | Critical path | `READ` | `ALLOW` | n/a |
| `CAP-015` | People / workload view | `READ` | `ALLOW` | n/a |
| `CAP-016` | Goals (OKR linkage) | `GOVERNED_WRITE` | `REQUIRE_APPROVAL` | usually |
| `CAP-017` | Sprints / backlog | `GOVERNED_WRITE` | `REQUIRE_APPROVAL` | usually |
| `CAP-018` | Custom fields | `GOVERNED_WRITE` | `REQUIRE_APPROVAL` | usually |
| `CAP-019` | Conditional coloring / formatting rules | `GOVERNED_WRITE` | `REQUIRE_APPROVAL` | usually |
| `CAP-020` | Calendar / working time | `GOVERNED_WRITE` | `REQUIRE_APPROVAL` | usually |
| `CAP-021` | Task history / conversations | `READ` | `ALLOW` | n/a |
| `CAP-022` | Portfolios / roadmaps | `GOVERNED_WRITE` | `REQUIRE_APPROVAL` | no (restructure) |
| `CAP-023` | Sharing / permissions | `DESTRUCTIVE` | `REQUIRE_APPROVAL` | no |
| `CAP-024` | Import / export | `DESTRUCTIVE` | `REQUIRE_APPROVAL` | no |
| `CAP-025` | Reporting / Power BI surface | `READ` | `ALLOW` | n/a |
| `CAP-026` | Account / license context | `READ` | `ALLOW` | n/a |

- **CAP-015.** Each `capability_key` SHALL appear at most once in the matrix; the key is the join
  column between this file, the UIContract, and the `capability_state` table.
- **CAP-016.** The `mutation_class` column SHALL agree with the `ExtendedToolManifest` entry for
  the tool that implements the row; a mismatch is a contract-breaking change
  (see [governance.md](governance.md) change control).

## CAP-017 — Discovery-to-support workflow

The canonical path that takes a row from `UNVERIFIED_LIVE` to `SUPPORTED`:

1. **Operator observation** — an operator opens the surface in the persistent profile and records
   a dated note → `DISCOVERED` (and `ui_contract_state` records the fragment as observed).
2. **Attestation campaign** — a read-only campaign resolves a locator uniquely against the live
   UI and stores evidence (`UI-002`, `GOV-042`). No campaign runs in CI against a real tenant
   (`UI-045`).
3. **UI_ATTESTED** — the contract fragment carries `{locator_strategies, expected_role,
   expected_text, expected_structure, read_back_probe}` with an attestation hash.
4. **READ_ATTESTED** — `planner_<domain>_get` / `planner_project_snapshot` returns schema-valid
   data and the read-back probe confirms it (`UI-060`).
5. **MUTATION_ATTESTED** — for mutating rows, a governed apply (dry-run → approval → apply)
   lands and read-back confirms; compensation is demonstrated against the mock UI.
6. **Governance publish** — a maintainer records a `GOV-010` decision (policy rule present, tests
   green, drift handling in place) → `SUPPORTED`. The tool is added to the `ToolManifest`.
7. **Ongoing** — `planner_ui_contract_status` and `planner_drift_report` monitor; any
   contradiction → `UI_DRIFT` (`UI-043`).

- **CAP-018.** A tool SHALL NOT be advertised in the `ToolManifest` for a row below `SUPPORTED`.
  Read-only tools may be advertised at `READ_ATTESTED` only when explicitly published as
  read-only (`GOV-010`).
- **CAP-019.** Each step SHALL be recorded in the attestation ledger (`ui_contract_state`,
  `capability_state`) with a timestamp and evidence hash so the advance is auditable
  (see [state-model.md](state-model.md)).

## CAP-020 — Per-capability read-back and drift detail

The matrix `Read-back strategy` column is summarised; the operational contract is:

| Row | Read-back probe | Failure / drift code | Notes |
| --- | --- | --- | --- |
| `CAP-003` create | re-read plan by name+owner, bind `external_id` | `UI_DRIFT` | no retry before read-back; binding created from observed id |
| `CAP-004` delete | re-read must return absent | `DESTRUCTIVE_DENIED` | explicit policy rule required |
| `CAP-005` WBS | re-read parent/child edges | `UI_DRIFT` | grid view; order matters (container before content) |
| `CAP-008` assignments | re-read assignee set | `BLOCKER_AMBIGUOUS_IDENTITY` | a person resolving to >1 principal is denied, never guessed |
| `CAP-009` dependencies | re-read edge type + lag on both ends | `BLOCKER_CYCLE` | acyclicity validated before apply |
| `CAP-011` duration/effort | re-read numeric field with unit | `BLOCKER_UNIT_AMBIGUOUS` | unit (h/d/w) ambiguity ⇒ deny |
| `CAP-012` scheduling | re-read computed dates after settle | `SCHEDULE_UNSETTLED` | non-settling recalculation ⇒ fail closed |
| `CAP-016` goals | re-read goal linkage | `UNSUPPORTED_TENANT` | Goals may be a separate license ⇒ block, not fail |
| `CAP-018` custom fields | re-read value + type | `BLOCKER_UNKNOWN_FIELD_TYPE` | unknown type ⇒ deny |
| `CAP-022` portfolios | re-read membership | `DESTRUCTIVE_RESTRUCTURE` | member move can cascade |
| `CAP-023` sharing | re-read member/role list | `DESTRUCTIVE_DENIED` | default deny; explicit rule |
| `CAP-024` import/export | full re-read diff vs blueprint | `IMPORT_OVERWRITE` | dry-run first; overwrite ⇒ approval |

- **CAP-021.** Every read-back SHALL be a fresh `PURE_READ` performed under the same lock held for
  the apply (see [idempotency.md](idempotency.md) read-back-before-retry).
- **CAP-022.** Read-back mismatch SHALL mark the operation `UNVERIFIED` and SHALL NOT trigger a
  blind retry; the affected `external_id`s are surfaced to the caller
  (see [reconciliation.md](reconciliation.md)).

## CAP-023 — Blocker and unsupported handling

- **CAP-023.** A capability that becomes unreachable due to device-compliance policy SHALL move
  to `BLOCKED_CONDITIONAL_ACCESS` and every dependent operation SHALL refuse with
  `BLOCKER_CONDITIONAL_ACCESS` (see [privacy-boundary.md](privacy-boundary.md) and
  `AUTH-072`).
- **CAP-024.** A capability absent or unlicensed in the tenant SHALL move to `UNSUPPORTED_TENANT`
  with a dated observation note; it SHALL NOT be re-attempted automatically.
- **CAP-025.** Blocked and unsupported rows SHALL still be reported in the `CapabilityManifest`
  (`planner_capabilities`) so clients can reason about reachability without probing the tenant.

## CAP-026 — Reporting, manifests and traceability

- **CAP-026.** `planner_capabilities` SHALL return the full matrix (states, blockers, contract
  version) as the `CapabilityManifest`; it is the machine-readable form of this file.
- **CAP-027.** State transitions SHALL be traceable to the evidence that justified them via the
  `evidence_hash` join to `ui_contract_state` and the attestation ledger
  (see [traceability.md](traceability.md)).
- **CAP-028.** Every `SUPPORTED` capability SHALL map to at least one `ToolManifest` tool, one
  policy rule in [governance.md](governance.md), and one test in the mock-UI suite; the trace is
  recorded in [traceability.md](traceability.md).

## CAP-027..CAP-029 — Normative invariants (consolidated)

- **CAP-029.** Microsoft Graph availability SHALL NOT determine support (restates ADR-006;
  `CAP-005`).
- **CAP-030.** When tenant policy refuses the device (conditional access / non-compliant), the
  correct outcome is a clear blocker report to the operator **plus** the affected capability rows
  moving to a blocked support state (`BLOCKER_CONDITIONAL_ACCESS` / `BLOCKED_CONDITIONAL_ACCESS`);
  the system SHALL NOT attempt enrolment, device registration, or any technical bypass
  (`AUTH-072`, `PRIV-021`…`PRIV-023`).
- **CAP-031.** No documentation-only change SHALL advance a capability's `Support level`
  (`GOV-011`); the matrix is evidence-driven end to end.

## CAP-032 — Maintenance and review cadence

- **CAP-032.** The matrix SHALL be reviewed at every minor version bump and after any UIContract
  version bump; rows whose attestation age exceeds `GOV-044`/`GOV-045` SHALL be reset to
  `UNVERIFIED_LIVE` before the release.
- **CAP-033.** New capabilities are appended as new `CAP-xxx` rows; existing row ids and keys are
  never renumbered or reused.
- **CAP-034.** Selectors never enter this file; if a maintainer is tempted to add one, the change
  belongs in the UIContract (`UI-001`, `UI-002`) and is governed by `GOV-040`…`GOV-045`.

---

*Status: specification (implementation-grade). All `CAP-xxx` rows are `PLANNED` unless a release
note attests live evidence (`GOV-090`). The matrix at the top is normative; the sections below are
its operational expansion.*
