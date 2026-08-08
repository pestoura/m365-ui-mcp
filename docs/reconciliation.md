# Reconciliation

Desired-state first. Callers declare intent keyed by a stable `external_id`; the engine observes
current state, computes a minimal diff and converges.

- `DesiredResource(external_id, kind, spec, source_id)`
- `diff(desired, observed) -> Diff | None` (None means converged)
- Actions: `create`, `update` (0.1.0 computes diffs but never applies them)

Reconciliation runs under typed resource locks and records checkpoints so a partially applied change
can be resumed or compensated by a saga.
