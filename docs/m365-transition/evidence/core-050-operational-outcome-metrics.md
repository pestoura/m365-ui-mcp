# CORE-050 — Drift/read-back/indeterminate metrics

Status: **IMPLEMENTED_AWAITING_CURRENT_BASE_GATES**

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

## Current integration gate

CORE-049 and all preceding Phase 5 work are merged. The current `main` is post-merge GREEN at `24e39ad2cf9372fcd218067bd8d6ad798773b52b`. This clean revision is based directly on that integration point so both standalone branch CI and pull-request merge CI validate the same corrected history; previous stacked GREEN evidence is not reused for merge.
