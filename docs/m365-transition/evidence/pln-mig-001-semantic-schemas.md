# PLN-MIG-001 — Planner semantic schemas in the application module

Status: **IMPLEMENTED_AWAITING_CURRENT_BASE_GATES**

## Objective

Extract the complete current Planner public semantic input/output schema surface into the Planner-owned M365 application boundary without changing any public contract.

## Implementation

`m365_mcp.apps.planner.schemas` now owns a bounded schema catalog for all 17 preserved `planner_*` public tools.

The catalog preserves exactly:

- empty-object input schemas for no-argument tools;
- opaque `plan_id` input schemas for plan/task-list/project-snapshot reads;
- opaque `task_id` input schema for task reads;
- the existing versioned read-result envelope;
- `read_only=true` and `graph_api_used=false` contract invariants.

Schema constructors return fresh objects so one operation cannot mutate schema state used by another.

## Transition boundary

This phase extracts schema ownership only. `PLN-MIG-002` moves Planner Tool Registry entries into the application module and can consume this catalog. Until then, parity tests compare the app-owned schema catalog against every current Planner Tool Registry definition.

## Compatibility

- exactly 17 public Planner schemas are represented;
- public `planner_*` names are unchanged;
- inputs and outputs are byte-semantically equivalent as Python schema objects to the current registry definitions;
- no Outlook capability is enabled;
- no browser primitive, secret or tenant content is introduced.

## Acceptance coverage

Tests prove full 17-tool schema parity, deterministic order, fresh-object isolation and fail-closed rejection of unreviewed identifier schema kinds.

The branch was re-triggered after the CORE-032 and OUT-001 merges. It is now re-triggered again after CORE-033 reached full post-merge GREEN, so the mandatory PR gates prove compatibility against the latest scope-aware policy integration base.
