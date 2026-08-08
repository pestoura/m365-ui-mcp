# State model

SQLite with `journal_mode=WAL`, `synchronous=FULL`, `foreign_keys=ON`, `busy_timeout=30000`.

| Table | Purpose |
| --- | --- |
| `schema_meta` | Schema version |
| `resource` | Desired vs observed state per `external_id` (+ `source_id`) |
| `resource_lock` | Typed resource locks |
| `idempotency` | Idempotency keys and result hashes |
| `saga` | Long-running operations |
| `checkpoint` | Saga step checkpoints (FK to `saga`, cascade) |
| `approval` | Approval records for `REQUIRE_APPROVAL` decisions |
| `audit_event` | Append-only audit trail |

No Planner content, credentials or session material is stored in 0.1.0.
