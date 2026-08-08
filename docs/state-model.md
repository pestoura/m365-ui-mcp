# State model

Persistent state lives in the control plane only (SQLite initially, migration-managed). The
worker is stateless apart from the browser profile it owns.

This document is the storage contract for the control plane. It specifies every persisted entity,
its columns and invariants, the typed-lock machinery that serialises writers, the snapshot and
idempotency structures that make reconciliation deterministic, the migration and retention rules
that keep the store trustworthy, and the privacy boundary that limits what is ever written to disk.
It is referenced by [reconciliation.md](reconciliation.md), [governance.md](governance.md),
[idempotency.md](idempotency.md), [security.md](security.md) (SEC-012, SEC-023) and requirement
R-09 / R-13 in [traceability.md](traceability.md).

## Entities

### auth_state
`state` (enum, see [authentication-and-mfa.md](authentication-and-mfa.md)), `reason_code`,
`profile_id`, `last_verified_at`, `expiry_hint`. **No cookies, tokens or session identifiers.**

Invariants:
- Exactly one row per `profile_id`; updated in place, never appended.
- `state` is the single source of truth for the auth gate (SEC-063). Any tenant-touching tool reads
  `auth_state.state` and refuses unless `AUTHENTICATED`.
- `expiry_hint` is derived, never authoritative; an expired hint does not auto-invalidate — the
  engine re-verifies against the live profile before trusting a stale `AUTHENTICATED`.
- `reason_code` is set on every non-`AUTHENTICATED` transition (e.g. `AUTH_FAILED`,
  `BLOCKER_CONDITIONAL_ACCESS`, `WAITING_FOR_MFA` timeout).

### binding
`source_id`, `external_id`, `entity_type` (`plan|bucket|task|dependency|assignment|custom_field|
sprint|goal|portfolio`), `plan_scope`, `first_seen`, `last_verified`, `evidence_hash`,
`status` (`BOUND|ORPHANED|AMBIGUOUS`).

Invariants:
- `(source_id, entity_type)` is unique per `plan_scope`.
- `external_id` may be null only when `status = ORPHANED` or `AMBIGUOUS`.
- `evidence_hash` pins the read that produced/confirmed the binding; it changes on every
  `last_verified` refresh.
- `status = AMBIGUOUS` is set by the adoption resolver (reconciliation.md §Identity) and blocks any
  operation on that `source_id` until disambiguated.

### operation
`operation_id`, `tool_name`, `fingerprint`, `mutation_class`, `policy_decision`, `approval_id`,
`state` (`PLANNED|IN_FLIGHT|APPLIED|READ_BACK_OK|INDETERMINATE|FAILED|COMPENSATED`),
`started_at`, `ended_at`, `error_code`, `contract_version`, `ui_contract_version`.

Invariants:
- `fingerprint` is the sha256 from idempotency.md; duplicates are suppressed at insert time.
- `approval_id` is non-null iff `policy_decision = REQUIRE_APPROVAL`.
- A row may advance `state` only along the operation transition graph (state-model.md §State
  transitions — operation); backward transitions are rejected by the store.
- `contract_version` and `ui_contract_version` are snapshotted at plan time and compared at apply
  time to detect `BLOCKER_UI_DRIFT` / `SNAPSHOT_STALE`.

### saga / saga_step
`saga_id`, `blueprint_id`, `state`, plus steps with `seq`, `operation_id`, `checkpoint_state`,
`compensation_state`.

Invariants:
- `saga.state` ∈ `PLANNED|IN_FLIGHT|COMPLETED|FAILED|COMPENSATED`.
- `saga_step.seq` is dense (no gaps) and defines execution order.
- `checkpoint_state` follows the operation checkpoint graph (reconciliation.md §Sagas);
  `compensation_state` ∈ `NONE|COMPENSATING|COMPENSATED|FAILED`.
- A saga is `COMPLETED` only when every step `checkpoint_state = READ_BACK_OK`.

### approval
As specified in [governance.md](governance.md). Single-use, fingerprint-bound, expiring.

### idempotency_record
`fingerprint`, `operation_id`, `state`, `result_hash`, `ttl`.

Invariants:
- `state` ∈ `IN_FLIGHT|COMPLETED|FAILED|INDETERMINATE`.
- `IN_FLIGHT` with the same `fingerprint` blocks a twin request (`OPERATION_IN_FLIGHT`).
- `COMPLETED` short-circuits the twin with the stored `result_hash` and performs no tenant action.
- `INDETERMINATE` requires `planner_reconcile_resume` before any other op touches those
  `external_id`s.
- Row is purged when `ttl` (default 7 days) elapses.

### lock
`resource_type`, `resource_id`, `mode` (`SHARED|EXCLUSIVE`), `holder_operation_id`,
`acquired_at`, `expires_at`.

Invariants:
- A `SHARED` lock coexists with other `SHARED` locks on the same resource; an `EXCLUSIVE` lock
  requires zero other locks of any mode.
- `expires_at` is a lease; an expired lock is treated as released. An operation whose lease expires
  mid-apply moves to `INDETERMINATE` (never silently continued).
- Locks are acquired in the fixed order below to prevent deadlock.

### ui_contract_state
`contract_version`, `fragment_id`, `attestation_status`, `evidence_hash`, `last_checked`,
`drift_state`.

Invariants:
- One row per `fragment_id`; `attestation_status` ∈ `UNATTESTED|ATTESTED|DRIFT`.
- `drift_state` is set by the drift detector (reconciliation.md §Drift); `DRIFT` downgrades any
  dependent capability to `UI_DRIFT`.
- `evidence_hash` anchors the selector proof; changing a selector requires a new attestation row,
  never an in-place edit of `evidence_hash`.

### capability_state
`capability_id`, `support_level`, `evidence_hash`, `updated_at`, `blocker_code`.

Invariants:
- `support_level` follows the capability state machine (planner-premium-capabilities.md).
- `blocker_code` is non-null only in blocker states; it names the typed blocker
  (`BLOCKER_CONDITIONAL_ACCESS`, `UNSUPPORTED_TENANT`, …).

## Typed locks

| Resource type | Granularity | Typical mode |
| --- | --- | --- |
| `browser_profile` | singleton | EXCLUSIVE for any worker operation touching the profile |
| `plan` | per plan `external_id` | SHARED for reads, EXCLUSIVE for writes |
| `bucket_set` | per plan | EXCLUSIVE |
| `task` | per task `external_id` | EXCLUSIVE |
| `dependency_graph` | per plan | EXCLUSIVE |
| `sprint` | per sprint | EXCLUSIVE |
| `portfolio` | per portfolio | EXCLUSIVE |
| `auth` | singleton | EXCLUSIVE during an auth flow |

Rules: locks are ordered (profile → plan → sub-resources) to prevent deadlock; every lock has a
lease with expiry; a write lock is held across apply **and** read-back; expired lease ⇒ the
operation is `INDETERMINATE`, never silently continued.

### Lock acquisition algorithm

```text
acquire(resource_set, mode):
  sort resource_set by (order_rank[resource_type], resource_id)   # fixed order, deadlock-free
  for r in resource_set:
    if mode == EXCLUSIVE:
      if any_lock(r): return BLOCKER_LOCK_CONFLICT   # never wait/spin
    else:  # SHARED
      if exclusive_lock(r): return BLOCKER_LOCK_CONFLICT
    insert lock(r, mode, lease=now+LOCK_LEASE)
  return OK

release(resource_set): delete locks where holder_operation_id = self
```

The engine never blocks waiting for a lock; a conflicting lock returns `BLOCKER_LOCK_CONFLICT`
immediately and the caller retries after backoff (idempotency.md §Retry policy). `LOCK_LEASE`
default is 120s; it is refreshed while an apply+read-back window is open. A crashed holder's locks
auto-expire and are reclaimed by the resume protocol (reconciliation.md §Crash recovery).

## State transitions — operation

```text
PLANNED -> IN_FLIGHT -> APPLIED -> READ_BACK_OK
                    \-> INDETERMINATE
                    \-> FAILED -> COMPENSATED
```

`READ_BACK_OK` is the only success terminal for a mutation. `INDETERMINATE` blocks further
operations on the affected `external_id`s until reconciled.

The store enforces this graph: an `UPDATE operations SET state=?` that would jump
`PLANNED→READ_BACK_OK` or `COMPENSATED→APPLIED` is rejected. `INDETERMINATE` and `FAILED` are
terminal for that `operation_id` until a reconcile produces a new `operation_id` (new fingerprint)
or a compensation closes the saga.

## Snapshots

`planner_project_snapshot` produces a composite read with a `snapshot_hash` over normalized
entity data. Blueprint applies pin a snapshot hash; a changed hash mid-run ⇒ `SNAPSHOT_STALE`.

Snapshot contents (privacy-bounded): for each entity in scope, the normalised field set used by the
diff (titles as hashes, dates/units as values, ids as opaque `external_id`s). Task bodies and
conversation text are **excluded** (SEC-072, state-model.md §Retention). `snapshot_hash` is
`sha256(canonical_json(normalised_entities))`; it is deterministic so two readers of the same
tenant state compute identical hashes.

## Migrations

Idempotent, forward-only, versioned; applied at startup with an advisory lock; schema version
recorded and exposed via `planner_readiness`. No destructive migration without an ADR.

### Migration framework

- A `schema_migrations` table tracks applied `(version, name, applied_at, checksum)`.
- At startup the engine takes a PostgreSQL/SQLite advisory lock keyed on a constant, applies every
  pending migration in `version` order, then releases.
- Each migration is wrapped so re-running it is a no-op if its `version` is already present
  (idempotent DDL via `CREATE TABLE IF NOT EXISTS`, additive columns only).
- A migration whose `checksum` changed after being applied is a hard startup failure (tamper
  signal), not a silent re-apply.
- Destructive migrations (drop column, change type in a lossy way) require an ADR reference in the
  migration name and a maintainer sign-off recorded in the PR (governance.md §Change control).
- `planner_readiness` reports `schema_version` and `migrations_pending`; it refuses tenant traffic
  until `migrations_pending = 0`.

## Retention

Operations, sagas and approvals retained for audit (default 180 days). Idempotency records expire
by TTL (default 7 days). Evidence artifacts are local files with their own retention, referenced
by hash. No tenant content is retained beyond what a binding requires (ids and hashes, not task
text) unless a snapshot is explicitly requested and cached with a short TTL.

Retention specifics:

| Entity | Retention | Basis | Redaction |
| --- | --- | --- | --- |
| `operation` | 180 days | audit trail (R-13) | tool name, class, decision, error code; no task text |
| `saga` / `saga_step` | 180 days | audit trail | ids + hashes only |
| `approval` | 180 days | audit + replay defence | approver, hash, no credential |
| `idempotency_record` | 7 days (TTL) | replay suppression | fingerprint + result hash |
| `binding` | indefinite while entity live | identity resolution | ids + hashes, never body |
| `auth_state` | rolling (1 row/profile) | auth gate | no secret material |
| `ui_contract_state` | indefinite | drift detection | fragment id + hash |
| `capability_state` | indefinite | matrix source of truth | ids + hashes |
| `lock` | lease-based (≤120s) | concurrency | transient |

A nightly job deletes rows past retention and compacts; deletion is recorded in the append-only
audit trail so removal is itself auditable (R-13). Snapshots, when cached, carry a TTL of 300s and
are never written to the long-term store.

## Privacy boundary (what is never stored)

- No cookies, tokens, `ESTSAUTH*`, refresh tokens, storage state, or session blobs (SEC-021,
  SEC-023). Those live only in the profile volume (SEC-012), which is never read into the control
  plane.
- No task title, description, conversation body, or assignee display name in persistent state.
  Titles are retained only as salts/hashes for logging (SEC-072); they are reconstructable only
  inside the worker's redacted evidence artefacts, which live outside git.
- No `source_id` value that embeds PII is required; callers are expected to use opaque keys.
- The profile volume is the only writable persistent surface in the worker (SEC-012) and is never
  copied, exported, committed, or transmitted.

## Isolation and consistency

- The control plane is single-writer for state mutations; the worker never writes state, it only
  returns reads/apply results over the internal channel.
- Each operation runs inside a transaction that spans the state writes for its checkpoint; a crash
  between checkpoint persist and tenant apply leaves the row at `APPLIED`/`IN_FLIGHT` and is resolved
  by the resume protocol, never by partial commit.
- Reads for read-back use `READ_BACK_OK`-grade consistency: they read the live tenant via the worker,
  not a possibly-stale control-plane cache.

## Requirement mapping

| Topic | Requirement / control |
| --- | --- |
| Normalised state for comparison | R-09 |
| Append-only, hash-chained audit | R-13, observability.md §6 |
| No secret material in state | SEC-012, SEC-021, SEC-023 |
| Bounded metric/label cardinality | R-12, SEC-073 |
| Typed locks across apply+read-back | SEC-066, reconciliation.md |
| Migration safety / fail closed | deployment.md §9, R-30 |
