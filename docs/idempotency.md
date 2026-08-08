# Idempotency

- Every future mutation carries an idempotency key persisted in the `idempotency` table.
- **Read-back before retry**: after a suspected failure the system re-reads observed state before
  retrying, to avoid duplicate effects on a UI-driven backend where responses can be lost.
- Idempotency classes: `pure_read` (all 0.1.0 tools), `idempotent_write`, `non_idempotent_write`.
- Non-idempotent writes require an approval and a saga with compensation.
