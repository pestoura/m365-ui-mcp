# CORE-014 — Per-fragment UI attestation

## Decision

UIContract attestation is now evaluated per explicit capability dependency instead of treating the complete Microsoft 365 UI selector set as one global support switch.

A fragment may declare semantic `capability_keys`. Only those declared dependencies participate in the UI evidence for that capability. Unknown or missing dependencies fail closed.

## Initial conservative dependency map

```text
planner.plan-surface
  -> plans.read
  -> project_snapshot.read

planner.task-surface
  -> tasks.read
  -> buckets.read
  -> project_snapshot.read
```

The current `common.auth` and `planner.account` fragments do not directly promote application capabilities. Authentication and account validity remain separate effective-evidence dimensions.

Capabilities such as dependencies, scheduling, goals, sprints, resources, custom fields and portfolios are deliberately **not inferred** from generic plan/task/account selectors. Until dedicated UI evidence exists, their UI dependency remains undeclared and their effective support stays fail-closed.

## Drift semantics

- all declared dependency fragments attested -> UI evidence `ATTESTED`;
- declared dependency exists but is unattested -> `UNVERIFIED_LIVE`;
- any declared dependency fragment is `DRIFTED` -> capability UI evidence is drifted;
- with all non-UI evidence valid, only capabilities depending on the drifted fragment become `DEGRADED`;
- unrelated capabilities retain their own independent UI state;
- missing auth/account/licence/live provenance still prevents a drifted capability from being presented as previously supported.

## Compatibility boundary

Planner's global `planner_ui_contract_status` remains available as a compatibility view. CORE-014 changes effective capability support, not the public tool set. CORE-015 owns the contract-set digest, so no digest or execution pinning is introduced here.
