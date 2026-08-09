# CORE-049 — UI execution metrics

Status: **IMPLEMENTED_AWAITING_CURRENT_BASE_GATES**

## Objective

Measure UI execution cost and reliability using low-cardinality semantic stages and numeric counters only, without collecting selectors, URLs, tenant content, mailbox/account identity, browser profile paths, or secrets.

## Metric dimensions

`UIExecutionStage` is closed to `NAVIGATION`, `READ`, `INTERACTION`, and `READ_BACK`.

`UIExecutionOutcome` is closed to `SUCCESS`, `BLOCKED`, `CONTRACT_MISMATCH`, `TIMEOUT`, and `FAILED`.

A sample records only application, stage, outcome, duration, interaction count, retry count, and read-back count. Negative counters fail closed.

## Aggregation

`aggregate_ui_execution_samples()` groups only by application/stage/outcome and sums numeric counters. The model deliberately has no selector, tool argument, URL, plan/task/message id, account, mailbox, tenant, profile, or free-form error label, preventing accidental high-cardinality telemetry.

## Relationship to adjacent phases

- CORE-048 measures context/result reduction economics.
- CORE-049 measures the UI execution mechanics themselves.
- CORE-050 covers drift/read-back/indeterminate operational outcomes.

## Acceptance coverage

Tests prove bounded projection, rejection of invalid numeric counters, deterministic low-cardinality aggregation, and separation of distinct outcome series.

## Dependency gate

CORE-048 is merged and the current `main` is post-merge GREEN at `cd64ad70c4a1608f1948d46be51eeef3506c3124`. This revision re-triggers the complete mandatory gate suite against that exact integration base; historical stacked/preventive GREEN evidence is not reused for merge.
