# PLN-MIG-002 — Planner Tool Registry ownership

Status: **PREIMPLEMENTED_STACKED_AWAITING_PLN_MIG_001**

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

## Dependency boundary

This work is stacked on PLN-MIG-001 and cannot merge before PLN-MIG-001 is merged and post-merge GREEN. It will then be retargeted to `main` and revalidated with fresh mandatory gates.

## Acceptance coverage

Tests prove that the application-owned 17-definition set is exactly the set composed by the canonical registry, retains schema/public-governance parity and does not activate Outlook.
