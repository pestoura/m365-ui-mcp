# PLN-MIG-005 — Planner worker operations into application adapter

Status: **PREIMPLEMENTED_STACKED_AWAITING_PLN_MIG_004**

## Objective

Move Planner-specific typed worker behavior out of the legacy `planner_browser_worker` FastAPI implementation and into an application-owned adapter without changing routes, operation names, capability guards, mock outputs or public contracts.

## Implementation

`m365_browser_worker.apps.planner.PlannerWorkerAdapter` now owns the five current Planner worker operations:

```text
planner.plan.list
planner.plan.get
planner.task.list
planner.task.get
planner.project.snapshot
```

The adapter is parameterized by:

- the current mock/live mode predicate;
- the existing capability guard;
- a narrow `PlannerDataProvider` protocol.

This keeps the application adapter independent from the legacy Planner package. The compatibility FastAPI shell injects the historical mock provider and delegates both legacy HTTP routes and the typed `/operations` dispatcher to the adapter.

## Compatibility

The following legacy routes remain unchanged:

```text
GET /planner/plans
GET /planner/plans/{plan_id}
GET /planner/tasks?plan_id=...
GET /planner/tasks/{task_id}
GET /planner/plans/{plan_id}/snapshot
```

The typed worker protocol is not widened. Authentication/account operations remain platform/compatibility-shell owned and are not claimed by the Planner adapter.

## Governance and safety

- no generic browser primitive is introduced;
- no URL/selector/XPath/JavaScript/header/cookie/token/storage-state input is added;
- live reads preserve the existing capability guards;
- mock mode remains deterministic and tenant-free;
- no mutation is enabled;
- no Outlook operation is introduced.

## Acceptance coverage

Tests prove:

- exact ownership of the five existing Planner worker operations;
- mock plan/task/snapshot output parity;
- live capability-guard parity;
- typed plan/task argument dispatch parity;
- auth/account operations remain outside the Planner adapter.

Existing worker/FastAPI regression tests continue to validate the compatibility shell.

## Dependency gate

This work is stacked on PLN-MIG-004. It must not merge until PLN-MIG-004 is merged and post-merge `main` is GREEN. It will then be retargeted to `main` and fully revalidated with all mandatory gates.
