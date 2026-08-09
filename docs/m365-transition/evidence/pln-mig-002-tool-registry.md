# PLN-MIG-002 — Planner Tool Registry ownership

Status: **INTEGRATED_ON_MAIN**

## Objective

Move the 17 preserved Planner Tool Registry definitions out of the generic M365 core and into the Planner application module without changing the canonical public surface or governance metadata.

## Implementation

`m365_mcp.apps.planner.tool_registry` now owns `planner_tool_definitions()` and consumes the application-owned semantic schemas introduced by PLN-MIG-001.

The generic `m365_mcp.tool_registry` retains only:

- closed mutation/implementation/compatibility enums;
- the application-neutral `ToolDefinition` schema;
- immutable-by-interface `ToolRegistry` validation/projection;
- composition of application-owned definitions.

`default_tool_registry()` composes its current public registry from `planner_tool_definitions()` through a local import, preventing the generic core from carrying Planner-specific tool declarations.

## Compatibility invariants

- exactly 17 Planner definitions remain present and ordered canonically;
- every public name remains `planner_*`;
- every current definition remains READ and `PRESERVE`;
- schemas are supplied by the Planner-owned PLN-MIG-001 catalog;
- risk class, implementation state, capability keys, UIContract dependencies, read-back and idempotency metadata remain unchanged;
- Outlook remains absent from the public Tool Registry.

## Current integration gate

PLN-MIG-001 is merged. PR #253 is now based directly on the current `main` and this revision intentionally re-triggers the full mandatory CI/security/images/SBOM suite before any merge.

## Acceptance coverage

Tests prove that the application-owned 17-definition set is exactly the set composed by the canonical registry, retains schema/public-governance parity and does not activate Outlook.

## Integration reconciliation

This requirement's delta is present in `main`. The mandatory CI gate set (compile/lint/type/contracts/tests, image build + Trivy + SBOM, filesystem/dependency/secret scanning) was GREEN on the merged pull request, and the full gate set was re-executed on post-merge `main` at `9b4a645`.

Mock mode only: no live Microsoft tenant was contacted, no capability is promoted to SUPPORTED by this record, Outlook stays RESERVED, and the 17-tool Planner public ABI is unchanged.
