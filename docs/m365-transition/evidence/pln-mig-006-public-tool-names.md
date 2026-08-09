# PLN-MIG-006 — Preserve Planner public tool names

Status: **INTEGRATED_ON_MAIN**

## Objective

Make the historical Planner public MCP tool-name sequence an explicit application-owned ABI contract while preserving all 17 existing `planner_*` names and their order.

## Preserved ABI

```text
planner_health
planner_readiness
planner_capabilities
planner_agent_card
planner_ui_contract_status
planner_auth_status
planner_auth_start
planner_auth_resume
planner_auth_session_info
planner_plan_list
planner_plan_get
planner_task_list
planner_task_get
planner_project_snapshot
planner_account_context
planner_license_capabilities
planner_smoke_test
```

`m365_mcp.apps.planner.public_surface.PLANNER_PUBLIC_TOOL_NAMES` is immutable and `planner_public_tool_names()` exposes the same canonical tuple.

## Compatibility invariants

- exactly 17 names are preserved;
- names and order match the effective Planner Tool Registry;
- names and order match legacy `planner_mcp.tools.TOOL_NAMES`;
- all Planner definitions remain `CompatibilityRequirement.PRESERVE`;
- no Outlook name is activated;
- no generic browser/executor public primitive is introduced;
- no behavior, schema, policy, capability or mutation semantics change.

## Current integration gate

PLN-MIG-005 is merged and `main` is post-merge GREEN at `f1a870820a8a939f4db57c659d85ba0cfcd173ed`. This clean revision contains only the Planner public-surface ABI declaration, its application export, tests and evidence. Merge only after standalone and pull-request mandatory CI/security/documentation/image/Trivy/SBOM gates are GREEN.

## Integration reconciliation

This requirement's delta is present in `main`. The mandatory CI gate set (compile/lint/type/contracts/tests, image build + Trivy + SBOM, filesystem/dependency/secret scanning) was GREEN on the merged pull request, and the full gate set was re-executed on post-merge `main` at `9b4a645`.

Mock mode only: no live Microsoft tenant was contacted, no capability is promoted to SUPPORTED by this record, Outlook stays RESERVED, and the 17-tool Planner public ABI is unchanged.
