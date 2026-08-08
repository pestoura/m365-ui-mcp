# Reconciliation

Reconciliation-first: callers declare **desired state**; the engine computes and converges a diff
(ADR-003). No tool asks the browser to "do a click" on faith.

This document is normative. It defines the reconciliation contract that every mutating and reading
tool depends on, the deterministic algorithm that carries desired state to observed state, the
normalisation rules that make comparisons trustworthy, the identity-binding procedure that prevents
duplicate or phantom entities, the saga/checkpoint machinery that makes partial failure recoverable,
and the drift/concurrency boundaries that force the engine to fail closed instead of guessing. It is
referenced by [state-model.md](state-model.md), [governance.md](governance.md),
[idempotency.md](idempotency.md), [security.md](security.md) (SEC-060..SEC-067) and requirement
R-06 / R-10 in [traceability.md](traceability.md).

## Loop

```text
declare desired state
  -> read current state (typed, schema-valid)
    -> diff (by external_id / source_id)
      -> plan ordered operations (dependency-aware)
        -> policy + approval gate
          -> acquire typed locks
            -> apply step (saga checkpoint per step)
              -> READ-BACK
                -> converged? yes -> commit checkpoint
                            no  -> bounded re-converge, else compensate + fail closed
```

The loop is the *only* path by which tenant state changes. A tool never performs a direct browser
mutation outside this loop; `SAFE_WRITE` and `GOVERNED_WRITE` operations both enter at the
"declare desired state" entry point and are indistinguishable downstream until the policy/approval
gate. `READ` operations terminate at the "read current state" node and never take a lock or a
checkpoint.

## Identity: external_id and source_id

- `source_id` — the caller's stable key for an entity in *their* model (blueprint id, Jira key,
  row id). Supplied by the caller, never invented by the engine.
- `external_id` — the stable identity of the entity in Planner as observed through the UI.
- The state DB holds the binding `(source_id ⇄ external_id, entity_type, plan_scope,
  first_seen, last_verified, evidence_hash)`.
- If a `source_id` has no binding and a matching entity exists by natural key, the engine
  **adopts** it only when the match is unique; ambiguity ⇒ `BLOCKER_AMBIGUOUS_MATCH`, never a
  create.
- If a binding exists but the `external_id` is absent on read, the entity is `ORPHANED`; the
  engine does not silently recreate.

### Identity resolution algorithm

Identity resolution runs once per entity in the desired state, before diffing, and produces one of
four outcomes for each `source_id`:

1. **BOUND** — a binding row exists and the `external_id` is present in the current read. Re-use
   the `external_id`; refresh `last_verified` and `evidence_hash` on commit.
2. **ORPHANED** — a binding row exists but the `external_id` is absent from the current read.
   The engine records `ORPHANED`, does **not** create a replacement entity, and reports the
   orphan in the dry-run output. A separate `planner_adopt_orphan` (or an explicit
   `allow_recreate=false` declaration) is required to resolve it; implicit recreation is forbidden.
3. **ADOPTED** — no binding exists, but exactly one current entity matches by natural key
   (name+owner for plans; name+parent for buckets; title+plan for tasks; edge signature for
   dependencies). The engine writes a new binding, marks `first_seen`, and proceeds. Adoption is
   recorded as an audit event with the matched `external_id`.
4. **CREATE** — no binding and no unique natural-key match. The engine allocates a new
   `external_id` on apply and writes the binding at `READ_BACK_OK`.

Ambiguity handling: when more than one current entity matches the natural key, the outcome is
`BLOCKER_AMBIGUOUS_MATCH`. The engine surfaces the candidate `external_id` set and stops; it never
picks the first candidate (SEC-062). The caller must disambiguate before re-submitting.

Natural-key match tables (authoritative; other fields are ignored for matching):

| entity_type | natural key |
| --- | --- |
| plan | `(normalized_title, owner_upn)` |
| bucket | `(plan_external_id, normalized_name)` |
| task | `(plan_external_id, bucket_external_id, normalized_title)` |
| dependency | `(predecessor_external_id, successor_external_id, type)` |
| assignment | `(task_external_id, person_key)` |
| custom_field | `(entity_external_id, field_name)` |
| sprint | `(plan_external_id, normalized_name)` |
| goal | `(plan_external_id, normalized_name)` |
| portfolio | `(normalized_name, owner_upn)` |

## Diff semantics

- Entity sets are compared per type: plans, buckets, tasks, dependency edges, assignments,
  custom-field values.
- Field-level diff uses normalized typed values (dates as RFC3339 date, effort with explicit
  unit, text trimmed). Normalisation failures are diffs the engine refuses to guess at.
- Dependency edges are compared as `(predecessor, successor, type, lag)` tuples; the planner
  validates acyclicity **before** any apply.
- Unknown fields present in Planner but absent from the desired state are left untouched unless
  the caller declares `strict: true`, which turns them into `DESTRUCTIVE` removals requiring
  approval.

### Normalisation rules

Normalisation is deterministic and idempotent (`normalise(x) == normalise(normalise(x))`). A value
that cannot be normalised yields a `NORMALISATION_FAILED` diff cell, which is treated as a hard
refusal for that field (never a best-effort coercion).

- **Text** — Unicode NFKC, trimmed, collapsed interior runs of whitespace to a single space. Titles
  are compared case-sensitively after normalisation; `source_id` and `external_id` are compared
  byte-exactly.
- **Dates** — parsed to RFC3339 `date` (`YYYY-MM-DD`) for calendar dates and
  `date-time` (with `Z` UTC) for timestamps. Timezone-naive inputs are rejected unless the plan
  scope declares a single timezone; mixed timezones in one blueprint are a `NORMALISATION_FAILED`.
- **Effort / duration** — stored as `(magnitude: number, unit: enum{minutes, hours, days, weeks})`.
  Unit ambiguity (e.g. a bare `8` with no unit) ⇒ `NORMALISATION_FAILED`; the engine never assumes
  hours.
- **Enums** — priority, status, dependency type (`FS|SS|SF|FF`) are mapped through a closed lookup;
  an unknown value ⇒ `NORMALISATION_FAILED`.
- **Person keys** — compared by the resolved `person_key` (stable directory id when available,
  otherwise normalised UPN). A person resolvable to two distinct directory ids is
  `BLOCKER_AMBIGUOUS_IDENTITY`.

### Diff object schema

```json
{
  "plan_scope": "plan_external_id_or_source",
  "by_type": {
    "plan":      { "create": [], "update": [], "adopt": [], "no_op": [], "delete": [] },
    "bucket":    { "create": [], "update": [], "adopt": [], "no_op": [], "delete": [] },
    "task":      { "create": [], "update": [], "adopt": [], "no_op": [], "delete": [] },
    "dependency":{ "create": [], "update": [], "adopt": [], "no_op": [], "delete": [] },
    "assignment":{ "create": [], "update": [], "adopt": [], "no_op": [], "delete": [] },
    "custom_field":{ "create": [], "update": [], "adopt": [], "no_op": [], "delete": [] }
  },
  "strict_drift": [],
  "normalisation_failures": [],
  "ambiguous_matches": [],
  "orphans": []
}
```

Each `update` carries `external_id`, `source_id`, the list of `changed_fields` with `before`/`after`
normalised values, and the `mutation_class` the field change resolves to. `strict_drift` lists
Planner-only fields when `strict: true`; each becomes a `DESTRUCTIVE` `delete`-class entry requiring
approval.

## Ordering

Operation planning is topological: containers before contents (plan → buckets → tasks),
tasks before dependency edges, structure before scheduling, scheduling before assignments.
Removals run in reverse order.

The concrete dependency partial order enforced by the planner:

1. plans (create/update)
2. buckets (create/update) — depends on its plan
3. tasks (create/update) — depends on its plan and bucket
4. dependency edges — depends on both endpoints existing
5. scheduling fields (start/finish, duration/effort) — depends on the task existing
6. assignments — depends on the task existing
7. custom fields — depends on the owning entity existing
8. removals in reverse: assignments, custom fields, dependency edges, tasks, buckets, plans

Acyclicity for dependency edges is checked with a topological sort over the *desired* graph; if a
cycle is present the whole apply is denied with `BLOCKER_CYCLIC_DEPENDENCY` before any step runs
(SEC-060 family). A dependency pointing at a `source_id` with no corresponding create or existing
binding is `BLOCKER_DANGLING_EDGE`.

## Sagas, checkpoints, compensation

- Each planned operation is a saga step with a persisted checkpoint: `PENDING`, `APPLIED`,
  `READ_BACK_OK`, `READ_BACK_MISMATCH`, `COMPENSATED`, `FAILED`.
- A step is only considered complete at `READ_BACK_OK`.
- On failure, compensation runs for steps that are reversible; irreversible steps are reported as
  residual state with the exact `external_id` list — never hidden.
- A crashed run resumes from the last checkpoint after re-reading current state; it never replays
  applied steps blindly.

### Checkpoint lifecycle

```text
PENDING ──apply──▶ APPLIED ──read-back──▶ READ_BACK_OK ──commit──▶ (terminal success)
   │                  │
   │                  └──read-back──▶ READ_BACK_MISMATCH ──bounded re-converge──▶ APPLIED
   │                                                                        └─exhausted──▶ COMPENSATED / FAILED
   └──apply error──▶ FAILED ──compensate──▶ COMPENSATED
```

- `APPLIED` means the browser action returned success but the effect is **not** yet trusted.
- `READ_BACK_OK` is the only trustable success state (R-06).
- `READ_BACK_MISMATCH` triggers re-convergence only when the diff is *narrowable* (the gap shrank);
  oscillation (gap not shrinking across two attempts) is treated as exhausted.
- `COMPENSATED` records, per step, the inverse action taken and its own read-back result.

### Compensation rules per entity type

| entity_type | reversible | compensation action |
| --- | --- | --- |
| plan | partial | if created here, delete; if only updated, restore prior normalised fields via update+read-back |
| bucket | yes | delete bucket (reverse of create) |
| task | yes | delete task (reverse of create) |
| dependency | yes | remove edge |
| assignment | yes | remove assignment |
| custom_field | partial | clear value to prior; type change may be irreversible |
| scheduling | yes | restore prior dates via update+read-back |
| portfolio | no (restructure risk) | reported as residual; `DESTRUCTIVE` compensation requires an explicit new approval |

Residual state (irreversible steps that could not be undone) is emitted in the result with the exact
`external_id` list and the `operation_id` that produced it. It is never hidden, never logged as a
success, and always raises an operator alert (R-40).

## Read-back before retry

A timed-out or ambiguous apply is **never** retried directly. The engine re-reads and decides:
landed ⇒ mark `READ_BACK_OK`; not landed ⇒ retry allowed under the retry policy; indeterminate ⇒
fail closed. See [idempotency.md](idempotency.md).

Read-back uses the `PURE_READ` path for the affected entity type and compares the normalised current
state to the normalised desired post-state. The three outcomes map exactly to the idempotency store
(`COMPLETED` / retryable / `INDETERMINATE`). Auth operations and `BLOCKER_CONDITIONAL_ACCESS` /
`AUTH_FAILED` are terminal and never retried (idempotency.md §Retry policy).

## Dry-run

`planner_blueprint_plan` returns the full ordered operation list with mutation classes, approval
requirements and predicted diffs, without touching the tenant. Import flows require a successful
dry-run before apply.

The dry-run result is the same diff object plus, for each step: `mutation_class`, the
`policy_decision` that *would* be produced (computed but not enforced), the `approval_id` slot that
*would* be required, the `lock` set that *would* be taken, and the estimated read-back strategy. No
checkpoint is persisted; the fingerprint is computed so a subsequent apply can be matched against the
dry-run to detect parameter drift (`SNAPSHOT_STALE` if the fingerprint differs). Dry-run is itself a
`PURE_READ` contract and requires no approval.

## Drift

Between plan and apply, the UI contract version and a snapshot hash are pinned. If either changes
mid-run, the run halts with `BLOCKER_UI_DRIFT` or `SNAPSHOT_STALE`; it does not adapt on the fly.

- `BLOCKER_UI_DRIFT` — the UIContract fragment version referenced at plan time no longer matches the
  live contract (a selector was re-attested or a drift event fired, SEC-060). The run stops; no step
  past the last `READ_BACK_OK` checkpoint is taken.
- `SNAPSHOT_STALE` — a `planner_project_snapshot` taken at plan time has a different `snapshot_hash`
  than a re-read at apply time, meaning concurrent human edits shifted the baseline. The run stops
  rather than overwrite unseen state (SEC-065).

Both are blockers, not retries. Resolution (re-plan from the new snapshot, or explicit human override)
is an out-of-band decision.

## Concurrency

Typed locks (see [state-model.md](state-model.md)) serialise writers per resource. Concurrent
human edits in the UI cannot be prevented; they are detected by read-back mismatch and surfaced
rather than overwritten.

The engine's view of concurrency has three sources:
1. **Internal** — another tool invocation in the same control plane; serialised by typed locks.
2. **Human-in-UI** — an operator editing in the live Planner tab; invisible until read-back.
3. **External automation** — another integration touching the same tenant; invisible until read-back.

Only (1) is preventable. (2) and (3) manifest as `READ_BACK_MISMATCH` and are handled by
re-convergence or fail-closed. The engine never assumes it owns the tenant; it assumes it may be one
of several writers and defends with read-back + drift detection.

## Crash recovery / resume protocol

On restart, the engine runs `planner_reconcile_resume`:

1. Load every saga in a non-terminal state (`PENDING`, `IN_FLIGHT`, `APPLIED`, `READ_BACK_MISMATCH`).
2. For each, re-read current state for the saga's `plan_scope` (fresh `PURE_READ`, new snapshot hash).
3. Recompute the diff from *desired* (still held in the saga) against the *fresh* current state.
4. Skip steps already at `READ_BACK_OK` (do not replay). Re-evaluate steps at `APPLIED`/`MISMATCH`
   with the new read-back.
5. If the UI contract version changed since the saga started ⇒ `BLOCKER_UI_DRIFT` the saga.
6. If the recalculated diff is empty ⇒ mark saga `COMPLETED`, emit audit event.
7. Otherwise continue from the first not-`READ_BACK_OK` step, re-acquiring locks.

A crashed run is therefore always convergent and never double-applies a verified step.

## Determinism and canonical ordering

Two identical desired-state declarations over the same current state must produce byte-identical
operation lists and fingerprints. Determinism is guaranteed by: stable natural-key sort order
(lexicographic on the normalised natural-key tuple), a fixed topological tie-break (entity type
order, then `source_id` sort), and canonical JSON in every fingerprint. This is what makes dry-run↔
apply matching, idempotency lookup, and approval binding reliable.

## Worked example

Desired: create plan `P1` (source `src:plan:1`), bucket `B1`, tasks `T1`,`T2` (source
`src:task:1`,`src:task:2`), dependency `T1 → T2` (FS).

1. Resolve identity: no bindings ⇒ all `CREATE`.
2. Diff: one create per type, one dependency edge, no updates.
3. Order: plan → bucket → tasks (T1,T2 by source sort) → dependency edge.
4. Gate: `plan.create` = `GOVERNED_WRITE` ⇒ `REQUIRE_APPROVAL`; `bucket`/`task` = `SAFE_WRITE` ⇒
   `ALLOW`; `dependency` = `GOVERNED_WRITE` ⇒ `REQUIRE_APPROVAL`.
5. Apply P1 → read-back by (title, owner) ⇒ `READ_BACK_OK`, binding written.
6. Apply B1 → read-back bucket set ⇒ `READ_BACK_OK`.
7. Apply T1, T2 → read-back task detail ⇒ `READ_BACK_OK`.
8. Apply dependency → read-back edge type+lag ⇒ `READ_BACK_OK`.
9. Saga `COMPLETED`. Any mismatch at step 7 would trigger re-converge or, if exhausted, compensate
   T1/T2 (delete) and report residual.

## Requirement mapping

| Topic | Requirement / control |
| --- | --- |
| Read-back verification of every mutation | R-06, SEC-065 |
| Drift classification and reporting | R-10, SEC-060, SEC-061 |
| Fail closed on ambiguity | SEC-062, SEC-064 |
| Reconciliation-first design | ADR-003 |
| Idempotent replay of verified steps | R-07, idempotency.md |
| Typed locks during apply+read-back | state-model.md, SEC-066 |
