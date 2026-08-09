# PLN-MIG-005 — Planner worker operations into application adapter

Status: **IMPLEMENTED_AWAITING_CURRENT_BASE_GATES**

## Objective

Move Planner-specific typed worker behavior out of the legacy `planner_browser_worker` FastAPI implementation and into an application-owned adapter without changing routes, operation names, capability guards, mock outputs or public contracts.

## Implementation

`m365_browser_worker.apps.planner.PlannerWorkerAdapter` owns the five current Planner worker operations:

```text
planner.plan.list
planner.plan.get
planner.task.list
planner.task.get
planner.project.snapshot
```

The adapter is parameterized by the current mock/live mode predicate, the existing capability guard and a narrow `PlannerDataProvider` protocol. The compatibility FastAPI shell injects the historical mock provider and delegates both legacy HTTP routes and the typed `/operations` dispatcher to the adapter.

## Compatibility

The following legacy routes remain unchanged:

```text
GET /planner/plans
GET /planner/plans/{plan_id}
GET /planner/tasks?plan_id=...
GET /planner/tasks/{task_id}
GET /planner/plans/{plan_id}/snapshot
```

Authentication/account operations remain compatibility-shell owned and are not claimed by the Planner adapter. The typed worker protocol is not widened.

## Governance and safety

- no generic browser primitive is introduced;
- no URL/selector/XPath/JavaScript/header/cookie/token/storage-state input is added;
- live reads preserve the existing capability guards;
- mock mode remains deterministic and tenant-free;
- no mutation is enabled;
- no Outlook operation is introduced.

## Acceptance coverage

Tests prove exact ownership of the five Planner operations, mock output parity, live capability-guard parity, typed argument dispatch parity and exclusion of auth/account operations. Existing worker/FastAPI regression tests continue to validate the compatibility shell.

## Current integration gate

PLN-MIG-004 is merged and `main` is post-merge GREEN at `f73ad7ec81d905734f6b94ad8e0ea11e483ca540`. This clean revision is based directly on that integration point and intentionally excludes unrelated stacked-branch rewrites of prior Planner tests. Merge only after standalone and pull-request mandatory CI/security/documentation/image/Trivy/SBOM gates are GREEN.
