# CORE-043 — Dry-run / policy simulation

Status: **IMPLEMENTED_AWAITING_CURRENT_BASE_GATES**

## Objective

Expose complete per-node policy outcomes for BATCH/DAG/RUNBOOK plans without executing browser operations, consuming approvals, writing idempotency/checkpoint state, or mutating Microsoft 365.

## Simulation model

`m365_mcp.policy_simulation.simulate_policy_plan()` reuses the canonical CORE-034 `evaluate_plan_policy()` path. Every node is therefore evaluated independently by the same metadata-driven, security-tier-aware and scope-aware policy engine used by direct policy checks.

The simulation projects for each node:

- node id and semantic tool;
- policy decision and reason;
- application;
- mutation class;
- CORE-032 security tier;
- capability keys;
- CORE-033 effective scope and scope reason;
- whether scope was derived;
- dependency ids;
- whether mutation was requested;
- `mutation_performed=false`.

The top-level result carries the aggregate policy disposition only as an informational summary plus explicit `dry_run=true` and `side_effects_performed=false`. The aggregate value is never an authorization shortcut and does not erase individual node outcomes.

## Fail-closed behavior

Simulation retains normal policy behavior:

- unknown tools are `DENY`;
- scope mismatch is `DENY`;
- mutation overrides remain subject to the current public mutation-disablement gate;
- approval requirements remain visible as `REQUIRE_APPROVAL`;
- every node is represented even when another node is denied.

The current 17 public Planner tools remain individually simulatable and retain their existing read policy results.

## Side-effect boundary

The simulation module has no dependency on:

- browser worker execution;
- Playwright;
- approval persistence/consumption;
- idempotency reservation/result association;
- saga/checkpoint persistence;
- SQLite;
- Microsoft 365 mutation APIs.

It only evaluates immutable plan metadata and policy state already supplied to the control plane.

## Security/privacy boundary

Outputs contain reviewed policy metadata only. No tenant content, request/result payload, mailbox address, raw Microsoft identifier, browser profile path, cookie, token or storage state is introduced.

## Acceptance coverage

Tests prove:

- complete per-node outcomes and dependency projection;
- `dry_run=true`, `side_effects_performed=false` and `mutation_performed=false`;
- tier/scope/capability metadata preservation;
- mutation-disablement is visible without execution;
- unknown tool and scope mismatch fail closed independently;
- aggregate DENY does not erase an ALLOW outcome on another node;
- the simulation implementation imports no execution/persistence dependencies;
- all 17 current Planner public tools are simulatable without mutation.

## Current integration gate

CORE-042 is merged into `main` at `b897077f01bd7a13428c36f479bd222f228a7a18`. This revision deliberately re-triggers the complete mandatory CI/security/image/Trivy/SBOM/documentation suite against that current integration base. CORE-043 will merge only after CORE-042 post-merge `main` is GREEN and these fresh PR gates are GREEN. Its completion closes Phase 4 and unlocks CORE-044 integration.
