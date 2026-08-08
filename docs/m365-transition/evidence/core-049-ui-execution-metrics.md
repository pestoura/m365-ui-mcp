# CORE-049 — UI execution metrics

Status: **PREIMPLEMENTED_STACKED_AWAITING_CORE_048**

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

This work is stacked on CORE-048 and cannot merge until CORE-048 and its predecessors are merged and post-merge GREEN.
