# Reconciliation

Reconciliation-first: callers declare **desired state**; the engine computes and converges a diff
(ADR-003). No tool asks the browser to "do a click" on faith.

## Loop

```
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

## Ordering

Operation planning is topological: containers before contents (plan → buckets → tasks),
tasks before dependency edges, structure before scheduling, scheduling before assignments.
Removals run in reverse order.

## Sagas, checkpoints, compensation

- Each planned operation is a saga step with a persisted checkpoint: `PENDING`, `APPLIED`,
  `READ_BACK_OK`, `READ_BACK_MISMATCH`, `COMPENSATED`, `FAILED`.
- A step is only considered complete at `READ_BACK_OK`.
- On failure, compensation runs for steps that are reversible; irreversible steps are reported as
  residual state with the exact `external_id` list — never hidden.
- A crashed run resumes from the last checkpoint after re-reading current state; it never replays
  applied steps blindly.

## Read-back before retry

A timed-out or ambiguous apply is **never** retried directly. The engine re-reads and decides:
landed ⇒ mark `READ_BACK_OK`; not landed ⇒ retry allowed under the retry policy; indeterminate ⇒
fail closed. See [idempotency.md](idempotency.md).

## Dry-run

`planner_blueprint_plan` returns the full ordered operation list with mutation classes, approval
requirements and predicted diffs, without touching the tenant. Import flows require a successful
dry-run before apply.

## Drift

Between plan and apply, the UI contract version and a snapshot hash are pinned. If either changes
mid-run, the run halts with `BLOCKER_UI_DRIFT` or `SNAPSHOT_STALE`; it does not adapt on the fly.

## Concurrency

Typed locks (see [state-model.md](state-model.md)) serialise writers per resource. Concurrent
human edits in the UI cannot be prevented; they are detected by read-back mismatch and surfaced
rather than overwritten.
