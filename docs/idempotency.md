# Idempotency

> **Document status:** Normative. **Companion docs:** [state-model.md](state-model.md) (operation
> lifecycle, locks), [reconciliation.md](reconciliation.md), [governance.md](governance.md)
> (mutation classes), [security.md](security.md#7-fail-closed-invariants) (SEC-065),
> [threat-model.md](threat-model.md#3-stride) (T10, T11).
> Browser automation has no transaction. Idempotency is achieved through **keys, fingerprints and
> read-back**, never through optimism.

Browser automation has no transaction. Idempotency is achieved through **keys, fingerprints and
read-back**, never through optimism.

## 1. Motivation and definition

A `<button>` click is not a database transaction. There is no `ROLLBACK`, no row lock, no
two-phase commit. If a mutation "succeeds" but the confirmation navigation times out, we cannot
know whether the tenant changed. If the caller retries, we may apply the change twice. If the
caller's network drops mid-apply, we may leave the tenant in a half-state.

Idempotency here means: **performing an operation N times has the same net effect as performing it
once**, for the cases where that is even meaningful. We guarantee it with three mechanisms:

1. **Keys** — a caller-supplied `source_id` (for creations) and a system-computed
   `fingerprint` (for everything) that let us recognise "this is the same request."
2. **Store** — a durable ledger of what we have already done, keyed by fingerprint, so a repeat
   is answered from history rather than re-applied.
3. **Read-back** — after any mutation we re-read the affected entity from the UI and compare to
   the desired post-state. There is no success without read-back.

## 2. Idempotency classes

| Class | Definition | Retry rule |
| --- | --- | --- |
| `PURE_READ` | No state change. | Freely retryable. |
| `NATURAL_IDEMPOTENT` | Applying twice yields the same state (set a field to a value). | Retry allowed after read-back confirms non-convergence. |
| `KEYED_IDEMPOTENT` | Creates/binds an entity identified by a caller key (`source_id`); duplicate suppressed by binding lookup. | Retry only via the key path. |
| `NON_IDEMPOTENT` | Repetition changes meaning (append a comment, add a duplicate edge, delete). | Never auto-retried. Requires read-back and an explicit new decision. |

Every tool declares its class in the ExtendedToolManifest.

### 2.1 Class examples in Planner Premium

| Operation | Class | Why |
| --- | --- | --- |
| `planner_task_list` | `PURE_READ` | read-only |
| set task title to "X" | `NATURAL_IDEMPOTENT` | second apply is a no-op |
| create plan with `source_id="proj-alpha"` | `KEYED_IDEMPOTENT` | duplicate create suppressed via binding |
| add a checklist item | `KEYED_IDEMPOTENT` | bound by (task, item text) key |
| add a dependency edge | `NON_IDEMPOTENT` | a second edge is a different graph state |
| delete a bucket | `NON_IDEMPOTENT` | cannot be "undeleted" by retry |
| append a comment | `NON_IDEMPOTENT` | repeats append, never converge |

## 3. Operation fingerprint

```
fingerprint = sha256(
  tool_name || contract_version || ui_contract_version ||
  canonical_json(normalized_arguments) || sorted(target_external_ids)
)
```

Used for: idempotency lookup, approval binding, duplicate-request suppression and audit
correlation. Canonicalisation: sorted keys, no whitespace, normalized dates/units, lowercase
identifiers where the UI is case-insensitive.

### 3.1 Canonicalisation rules (normative)

- **Key order:** JSON object keys sorted lexicographically (deterministic serialiser, e.g.
  `json.dumps(obj, sort_keys=True, separators=(",", ":"))`).
- **Whitespace:** none in the canonical string.
- **Dates:** ISO-8601 `RFC3339`, normalised to UTC, no fractional trailing zeros.
- **Units:** durations normalised to a canonical unit (e.g. minutes) before serialisation; the
  canonical unit is recorded in the contract so both sides agree.
- **Identifiers:** `external_id`s lowercased where the UI treats them case-insensitively; the
  `target_external_ids` list is sorted before hashing.
- **Excluded:** `source_id` is *not* part of the fingerprint for `KEYED_IDEMPOTENT` creations
  (two different `source_id`s that resolve to the same `external_id` are different requests but
  both resolve via the binding lookup); transient fields (`request_id`, timestamps, caller
  session) are excluded.

### 3.2 Fingerprint examples

```
tool_name             = "planner_task_update"
contract_version      = "1.0.0"
ui_contract_version   = "2.1.0"
normalized_arguments  = {"task_id":"T-123","title":"Ship v1"}
target_external_ids   = ["T-123"]

canonical =
  planner_task_update|1.0.0|2.1.0|{"task_id":"T-123","title":"Ship v1"}|T-123
fingerprint = sha256(canonical)  ->  "sha256:9f2c…"
```

```
# A title-only change vs a due-date change are DIFFERENT fingerprints:
{"task_id":"T-123","title":"Ship v1"}   !=  {"task_id":"T-123","due":"2026-09-01T00:00:00Z"}
```

## 4. Idempotency store

`(fingerprint, operation_id, state, result_hash, created_at, completed_at, ttl)` with states
`IN_FLIGHT`, `COMPLETED`, `FAILED`, `INDETERMINATE`.

- A request whose fingerprint is `IN_FLIGHT` is rejected with `OPERATION_IN_FLIGHT` — not queued
  behind a possibly-successful twin.
- A request whose fingerprint is `COMPLETED` returns the stored result and performs no tenant
  action.
- `INDETERMINATE` requires an explicit reconcile (`planner_reconcile_resume`) before anything
  else touches those `external_id`s.

### 4.1 Store schema (state-model link)

Mirrors `idempotency_record` in [state-model.md](state-model.md): `fingerprint` (PK),
`operation_id`, `state`, `result_hash`, `ttl`. Indexed on `fingerprint` and on `state` for
sweeping expired/in-flight entries. TTL default 7 days; an `IN_FLIGHT` entry whose lease expires
without transition is swept to `INDETERMINATE` (never silently continued — see §6.3).

### 4.2 Concurrent request handling

| Existing record state | Incoming request | Behaviour |
| --- | --- | --- |
| none | first | create `IN_FLIGHT`, proceed |
| `IN_FLIGHT` | duplicate fingerprint | reject `OPERATION_IN_FLIGHT` |
| `COMPLETED` | duplicate fingerprint | return stored result, no tenant action |
| `FAILED` | duplicate fingerprint | return stored failure (caller may start a new op with a new decision) |
| `INDETERMINATE` | any touching same `external_id`s | reject until `planner_reconcile_resume` |

This prevents lost-update and double-apply even under at-least-once MCP delivery.

## 5. Read-back before retry (mandatory)

On timeout, navigation error, or any ambiguous outcome:

1. Release nothing; keep the lock.
2. Re-read the target entity/entities with a `PURE_READ` path.
3. Compare against desired post-state.
   - matches ⇒ `COMPLETED`, no retry;
   - clearly unchanged ⇒ retry permitted if class allows and the retry budget is intact;
   - partial/unclear ⇒ `INDETERMINATE`, fail closed, surface `external_id`s.

### 5.1 Comparison semantics

- The re-read is normalised with the **same canonicalisation** used for the fingerprint's
  `target_external_ids` and for desired-state comparison, so unit/format drift does not produce
  false mismatches.
- A "match" means every field the operation intended to change is observed at the desired value
  **and** no field the operation did not intend to change has moved in a way the contract forbids.
- "Partial/unclear" includes: entity missing when it should exist, value present but
  semantically ambiguous (e.g. two tasks with the same title), or a UI state that no longer
  matches the attested contract (`UI_DRIFT`).

## 6. Retry policy

- Only `PURE_READ`, `NATURAL_IDEMPOTENT` and key-path `KEYED_IDEMPOTENT` operations retry.
- Max 3 attempts, exponential backoff with jitter (base 1s, cap 15s), overall operation deadline.
- Retries never re-derive selectors, never relax attestation, never widen scope.
- Auth operations are **not** retried automatically; `BLOCKER_CONDITIONAL_ACCESS` and
  `AUTH_FAILED` are terminal for the attempt.

### 6.1 What counts as transient

| Signal | Transient? | Reason |
| --- | --- | --- |
| Network timeout to worker (B3) | Yes (read/class-allowed only) | transport; read-back confirms effect |
| Navigation timeout in UI | Yes (after read-back) | may have applied |
| `UI_DRIFT` | **No** | fail closed; re-attest instead |
| `AUTH_FAILED` / `BLOCKER_CONDITIONAL_ACCESS` | **No** | terminal; human/organisational |
| Policy `DENY` | **No** | not a retry target |
| Selector not found (attested) | **No** | drift; do not guess |

### 6.2 Backoff parameters

- `base_delay = 1s`, `cap = 15s`, `multiplier = 2`, `jitter = ±base_delay`.
- Attempt schedule example: 1s±1, 2s±2, 4s±4 … capped at 15s.
- Overall operation deadline bounds total elapsed time; exceeding it moves the op to
  `INDETERMINATE` and triggers read-back.

### 6.3 Lease and sweep

- An `IN_FLIGHT` record carries a lease. If the owning operation crashes, the lease expires and a
  sweep transitions the record to `INDETERMINATE`. The affected `external_id`s remain blocked
  until reconciled — we never assume the twin "probably succeeded."

## 7. Circuit breakers

Per operation family (auth, plan-read, task-read, task-write, schedule-write, portfolio):

- open after 5 consecutive failures or any `UI_DRIFT`/Conditional-Access blocker;
- half-open probe uses a `PURE_READ` only;
- while open, calls fail fast with `CIRCUIT_OPEN` and the reason code.

### 7.1 Breaker state machine

```
CLOSED --(5 consecutive failures OR UI_DRIFT/CA blocker)--> OPEN
OPEN   --(cooldown expires)--> HALF_OPEN
HALF_OPEN --(probe PURE_READ fails)--> OPEN
HALF_OPEN --(probe PURE_READ succeeds)--> CLOSED
```

- **Per-family scope:** a schedule-write storm does not disable plan reads.
- **Probe restriction:** only a `PURE_READ` probe is allowed while half-open, so we never attempt
  a mutation against a possibly-degraded tenant.
- **Reason code:** `CIRCUIT_OPEN` carries the family and the last trigger so operators can see
  *why* (e.g. `UI_DRIFT@task-write`).

## 8. Locks

Idempotency does not replace locking. Writes take the typed exclusive lock for their resource
scope for the whole apply + read-back window (see [state-model.md](state-model.md)).

### 8.1 Lock interaction rules

- **Ordering:** `browser_profile → plan → sub-resources` to prevent deadlock.
- **Mode:** `EXCLUSIVE` for any write; `SHARED` for reads on the same plan.
- **Lease:** every lock has an expiry; an expired lease ⇒ the operation is `INDETERMINATE`, never
  silently continued.
- **Hold window:** the write lock is held across **apply and read-back** — released only after
  `READ_BACK_OK` (or terminal failure). This is what makes concurrent same-entity writes safe
  even when idempotency keys differ.
- **Profile singleton:** any worker operation touching the profile takes the `browser_profile`
  `EXCLUSIVE` lock, serialising all tenant contact.

## 9. Sagas and compensation

For multi-step mutations (e.g. create portfolio → add plans → set dependencies), a **saga**
groups operations with checkpoints and compensations ([state-model.md](state-model.md#entities)
`saga`/`saga_step`). Idempotency applies per step; the saga records `checkpoint_state` so a
failure mid-run can be compensated or resumed.

- A `DESTRUCTIVE` step always requires an approval and a **compensation plan** (how to undo) before
  apply.
- A saga that hits `INDETERMINATE` at a step pauses; `planner_reconcile_resume` drives it forward
  or rolls back via compensations.

## 10. Failure taxonomy & error codes

| Code | Meaning | Retry? | State |
| --- | --- | --- | --- |
| `OPERATION_IN_FLIGHT` | duplicate fingerprint already running | no (wait or poll) | `IN_FLIGHT` |
| `ALREADY_COMPLETED` | duplicate fingerprint, result returned | no | `COMPLETED` |
| `INDETERMINATE` | outcome unknown after timeout | no (reconcile) | `INDETERMINATE` |
| `CIRCUIT_OPEN` | family breaker open | no (cooldown) | n/a |
| `UI_DRIFT` | contract mismatch | no (re-attest) | fail closed |
| `AUTH_FAILED` / `BLOCKER_CONDITIONAL_ACCESS` | auth terminal | no | terminal |
| `READ_BACK_MISMATCH` | read-back ≠ desired | no (discrepancy) | open discrepancy |

All are returned as stable codes with a human-readable reason; never a raw exception or DOM
fragment (SEC-075).

## 11. Worked examples

### 11.1 Duplicate create suppressed

1. Caller issues `create_plan(source_id="alpha", name="Alpha")`. Fingerprint `F1`, no record →
   `IN_FLIGHT`, apply, read-back → `COMPLETED`, binding `alpha → P-1`.
2. Caller (retries/at-least-once) issues same `source_id`. Fingerprint `F1` → `COMPLETED` →
   returns existing `P-1`, **no second plan created**.

### 11.2 Timeout with partial apply

1. `set dependency(T-1 → T-2)`. Apply navigates, but confirmation times out.
2. Keep lock; read-back. Edge present → `COMPLETED`. No retry.
3. If edge **absent** and class is `NON_IDEMPOTENT` → `INDETERMINATE`, surface `T-1`/`T-2`,
   require explicit reconcile. Never blind retry.

### 11.3 Circuit open

1. Five consecutive `task-write` `UI_DRIFT` events → breaker `OPEN` for `task-write`.
2. Next `task-write` → `CIRCUIT_OPEN` (reason `UI_DRIFT@task-write`) fast-fail.
3. Cooldown → `HALF_OPEN` → `PURE_READ` probe succeeds → `CLOSED`.

## 12. Testing strategy & invariants

- **Duplicate suppression:** same fingerprint twice → exactly one tenant effect (assert via mock
  UI state).
- **Fingerprint stability:** identical normalised input → identical hash across runs/processes.
- **Read-back mandatory:** a mutation that skips read-back cannot reach a success terminal.
- **Lock hold:** write lock present during read-back; released only after terminal state.
- **Circuit:** breaker opens on threshold, probes `PURE_READ` only, recovers.
- **In-flight rejection:** concurrent identical fingerprint → second rejected, not queued.
- **Indeterminate blocks:** `INDETERMINATE` on `external_id` blocks further ops until reconcile.

## 13. Configuration knobs

| Knob | Default | Notes |
| --- | --- | --- |
| `max_attempts` | 3 | total per operation |
| `backoff_base` / `backoff_cap` | 1s / 15s | exponential + jitter |
| `operation_deadline` | env-tuned | bounds elapsed; expiry → `INDETERMINATE` |
| `idempotency_ttl` | 7 days | record retention |
| `breaker_threshold` | 5 | consecutive failures to open |
| `breaker_cooldown` | env-tuned | OPEN → HALF_OPEN |

## 14. References

- [state-model.md](state-model.md) — operation lifecycle, typed locks, saga.
- [reconciliation.md](reconciliation.md) — plan/apply/verify loop, `planner_reconcile_resume`.
- [governance.md](governance.md) — mutation classes, approvals.
- [security.md](security.md#7-fail-closed-invariants) — SEC-065 read-back mismatch.
- [threat-model.md](threat-model.md#3-stride) — T10 (replay), T11 (duplicate mutation).
