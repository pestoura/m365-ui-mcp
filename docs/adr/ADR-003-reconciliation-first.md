# ADR-003 — Reconciliation-first with mandatory read-back

- Status: Accepted
- Date: 2026-08-08

## Context

Browser automation offers no transactions, no request ids and no server-side idempotency. A click
that times out may or may not have landed. Naïve retry produces duplicate tasks, duplicate
dependency edges and corrupted schedules — exactly the failures that destroy trust in an agent
operating a real project.

## Decision

All mutation is expressed as **desired state over stable identities**, and every applied step is
verified by a **read-back** before it is considered complete.

1. Caller declares desired state keyed by `source_id`; the engine maintains `source_id ⇄
   external_id` bindings.
2. The engine reads current state, computes a typed diff, and plans an ordered operation list
   (containers → contents → edges → schedule → assignments).
3. Each step passes policy/approval, takes a typed lock, applies, then **re-reads**.
4. `READ_BACK_OK` is the only success terminal. Mismatch ⇒ bounded re-converge, else compensate
   and fail closed.
5. On timeout or ambiguity the engine **never retries directly** — it re-reads and then decides:
   landed, not landed, or `INDETERMINATE` (fail closed, enumerate affected ids).
6. Runs are sagas with persisted checkpoints and resume from the last checkpoint after re-reading.

Idempotency classes (`PURE_READ`, `NATURAL_IDEMPOTENT`, `KEYED_IDEMPOTENT`, `NON_IDEMPOTENT`)
determine whether a retry is permissible at all.

## Consequences

- Duplicate creation is structurally prevented by binding lookup rather than by hope.
- Every mutation costs at least one extra read; accepted.
- Concurrent human edits are detected as read-back mismatches and surfaced instead of being
  overwritten.
- Requires stable identity extraction from the UI — a hard prerequisite, tracked by P-049.

## Rejected alternatives

- Fire-and-forget with retry — produces duplicates.
- Optimistic apply with eventual repair — leaves a corrupt project visible to humans in between.
- Client-supplied idempotency keys only — insufficient without a read-back, because the failure
  mode is uncertainty about the tenant, not about the request.

## Related

[docs/reconciliation.md](../reconciliation.md), [docs/idempotency.md](../idempotency.md),
[docs/state-model.md](../state-model.md); backlog P-031, P-049, P-050.
