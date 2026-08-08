# Idempotency

Browser automation has no transaction. Idempotency is achieved through **keys, fingerprints and
read-back**, never through optimism.

## Idempotency classes

| Class | Definition | Retry rule |
| --- | --- | --- |
| `PURE_READ` | No state change. | Freely retryable. |
| `NATURAL_IDEMPOTENT` | Applying twice yields the same state (set a field to a value). | Retry allowed after read-back confirms non-convergence. |
| `KEYED_IDEMPOTENT` | Creates/binds an entity identified by a caller key (`source_id`); duplicate suppressed by binding lookup. | Retry only via the key path. |
| `NON_IDEMPOTENT` | Repetition changes meaning (append a comment, add a duplicate edge, delete). | Never auto-retried. Requires read-back and an explicit new decision. |

Every tool declares its class in the ExtendedToolManifest.

## Operation fingerprint

```
fingerprint = sha256(
  tool_name || contract_version || ui_contract_version ||
  canonical_json(normalized_arguments) || sorted(target_external_ids)
)
```

Used for: idempotency lookup, approval binding, duplicate-request suppression and audit
correlation. Canonicalisation: sorted keys, no whitespace, normalized dates/units, lowercase
identifiers where the UI is case-insensitive.

## Idempotency store

`(fingerprint, operation_id, state, result_hash, created_at, completed_at, ttl)` with states
`IN_FLIGHT`, `COMPLETED`, `FAILED`, `INDETERMINATE`.

- A request whose fingerprint is `IN_FLIGHT` is rejected with `OPERATION_IN_FLIGHT` — not queued
  behind a possibly-successful twin.
- A request whose fingerprint is `COMPLETED` returns the stored result and performs no tenant
  action.
- `INDETERMINATE` requires an explicit reconcile (`planner_reconcile_resume`) before anything
  else touches those `external_id`s.

## Read-back before retry (mandatory)

On timeout, navigation error, or any ambiguous outcome:

1. Release nothing; keep the lock.
2. Re-read the target entity/entities with a `PURE_READ` path.
3. Compare against desired post-state.
   - matches ⇒ `COMPLETED`, no retry;
   - clearly unchanged ⇒ retry permitted if class allows and the retry budget is intact;
   - partial/unclear ⇒ `INDETERMINATE`, fail closed, surface `external_id`s.

## Retry policy

- Only `PURE_READ`, `NATURAL_IDEMPOTENT` and key-path `KEYED_IDEMPOTENT` operations retry.
- Max 3 attempts, exponential backoff with jitter (base 1s, cap 15s), overall operation deadline.
- Retries never re-derive selectors, never relax attestation, never widen scope.
- Auth operations are **not** retried automatically; `BLOCKER_CONDITIONAL_ACCESS` and
  `AUTH_FAILED` are terminal for the attempt.

## Circuit breakers

Per operation family (auth, plan-read, task-read, task-write, schedule-write, portfolio):

- open after 5 consecutive failures or any `UI_DRIFT`/Conditional-Access blocker;
- half-open probe uses a `PURE_READ` only;
- while open, calls fail fast with `CIRCUIT_OPEN` and the reason code.

## Locks

Idempotency does not replace locking. Writes take the typed exclusive lock for their resource
scope for the whole apply + read-back window (see [state-model.md](state-model.md)).
