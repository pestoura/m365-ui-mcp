# State model

Persistent state lives in the control plane only (SQLite initially, migration-managed). The
worker is stateless apart from the browser profile it owns.

## Entities

### auth_state
`state` (enum, see [authentication-and-mfa.md](authentication-and-mfa.md)), `reason_code`,
`profile_id`, `last_verified_at`, `expiry_hint`. **No cookies, tokens or session identifiers.**

### binding
`source_id`, `external_id`, `entity_type` (`plan|bucket|task|dependency|assignment|custom_field|
sprint|goal|portfolio`), `plan_scope`, `first_seen`, `last_verified`, `evidence_hash`,
`status` (`BOUND|ORPHANED|AMBIGUOUS`).

### operation
`operation_id`, `tool_name`, `fingerprint`, `mutation_class`, `policy_decision`, `approval_id`,
`state` (`PLANNED|IN_FLIGHT|APPLIED|READ_BACK_OK|INDETERMINATE|FAILED|COMPENSATED`),
`started_at`, `ended_at`, `error_code`, `contract_version`, `ui_contract_version`.

### saga / saga_step
`saga_id`, `blueprint_id`, `state`, plus steps with `seq`, `operation_id`, `checkpoint_state`,
`compensation_state`.

### approval
As specified in [governance.md](governance.md). Single-use, fingerprint-bound, expiring.

### idempotency_record
`fingerprint`, `operation_id`, `state`, `result_hash`, `ttl`.

### lock
`resource_type`, `resource_id`, `mode` (`SHARED|EXCLUSIVE`), `holder_operation_id`,
`acquired_at`, `expires_at`.

### ui_contract_state
`contract_version`, `fragment_id`, `attestation_status`, `evidence_hash`, `last_checked`,
`drift_state`.

### capability_state
`capability_id`, `support_level`, `evidence_hash`, `updated_at`, `blocker_code`.

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

## State transitions — operation

```
PLANNED -> IN_FLIGHT -> APPLIED -> READ_BACK_OK
                    \-> INDETERMINATE
                    \-> FAILED -> COMPENSATED
```

`READ_BACK_OK` is the only success terminal for a mutation. `INDETERMINATE` blocks further
operations on the affected `external_id`s until reconciled.

## Snapshots

`planner_project_snapshot` produces a composite read with a `snapshot_hash` over normalized
entity data. Blueprint applies pin a snapshot hash; a changed hash mid-run ⇒ `SNAPSHOT_STALE`.

## Migrations

Idempotent, forward-only, versioned; applied at startup with an advisory lock; schema version
recorded and exposed via `planner_readiness`. No destructive migration without an ADR.

## Retention

Operations, sagas and approvals retained for audit (default 180 days). Idempotency records expire
by TTL (default 7 days). Evidence artifacts are local files with their own retention, referenced
by hash. No tenant content is retained beyond what a binding requires (ids and hashes, not task
text) unless a snapshot is explicitly requested and cached with a short TTL.
