# PLN-MIG-003 — Planner capability definitions

Status: **INTEGRATED_ON_MAIN**

## Objective

Move the 11 preserved Planner scoped capability definitions out of the generic M365 core and into the Planner application module without changing capability identity, scope or policy behavior.

## Implementation

`m365_mcp.apps.planner.capability_registry` owns `planner_capability_definitions()` with the canonical 11 capability keys and their existing container scopes.

The generic `m365_mcp.capability_registry` retains the application-neutral `ScopedCapability` schema, registry validation/query API and composition function. `default_capability_registry()` composes current definitions from the Planner application module while preserving CORE-012's evidence-based support boundary.

## Preserved capability set

```text
plans.read                 account
tasks.read                 plan
buckets.read               plan
dependencies.read          plan
scheduling.read            plan
goals.read                  plan
sprints.read                plan
resources.read             plan
custom_fields.read         plan
portfolios.read            account
project_snapshot.read      plan
```

Every definition remains bound to `application=planner`, `surface=planner_web` and `account_scope=professional_session`.

## Compatibility and governance

- exactly 11 Planner capabilities are preserved;
- deterministic order and scope identity are preserved;
- Outlook remains absent from the effective Capability Registry;
- CORE-033 scope-aware policy continues to derive bounded scope for all 17 preserved Planner tools;
- no capability is promoted to live support by this ownership migration.

## Current integration gate

Phase 5 through CORE-050 is merged and the current `main` is post-merge GREEN at `d9865c672873440fa9162ea52311a244603b07f1`. This clean revision is built directly from that baseline so the Planner ownership migration cannot reintroduce stale stacked-branch history. Merge only after all mandatory CI/security/docs/image/Trivy/SBOM gates pass.

## Integration reconciliation

This requirement's delta is present in `main`. The mandatory CI gate set (compile/lint/type/contracts/tests, image build + Trivy + SBOM, filesystem/dependency/secret scanning) was GREEN on the merged pull request, and the full gate set was re-executed on post-merge `main` at `9b4a645`.

Mock mode only: no live Microsoft tenant was contacted, no capability is promoted to SUPPORTED by this record, Outlook stays RESERVED, and the 17-tool Planner public ABI is unchanged.
