# CORE-050 — Drift/read-back/indeterminate metrics

Status: **PREIMPLEMENTED_STACKED_AWAITING_CORE_049**

## Objective

Measure configuration drift, read-back reconciliation and indeterminate execution outcomes using only closed low-cardinality labels and occurrence counters.

## Closed dimensions

`OperationalSignal`:

```text
DRIFT
READ_BACK
INDETERMINATE
```

`OperationalOutcome` is constrained per signal:

- DRIFT: `CLEAN`, `DETECTED`, `RESOLVED`;
- READ_BACK: `EFFECT_PRESENT`, `EFFECT_ABSENT`, `AMBIGUOUS`;
- INDETERMINATE: `DETECTED`, `RESOLVED`.

Invalid signal/outcome combinations fail closed. Occurrence counts must be positive.

## Aggregation

Samples aggregate only by application/signal/outcome. There is no field for resource id, mailbox/account, selector, URL, error text, tenant identifier, profile, operation id or other high-cardinality data.

## Relationship to prior phases

- CORE-038 defines read-back-aware retry outcomes;
- CORE-042 defines the `INDETERMINATE` terminal state;
- CORE-049 measures UI execution mechanics;
- CORE-050 provides the operational outcome counters needed to observe reconciliation and uncertainty over time.

## Acceptance coverage

Tests prove valid projections, rejection of invalid signal/outcome pairs, positive occurrence invariants, deterministic aggregation and independent detected/resolved indeterminate counters.

## Dependency gate

This work is stacked on CORE-049 and cannot merge until CORE-049 and all preceding Phase 5 work are merged and post-merge GREEN.
