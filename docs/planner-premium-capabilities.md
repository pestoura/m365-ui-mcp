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
