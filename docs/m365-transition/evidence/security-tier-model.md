# CORE-032 — Security tier model

Status: **IMPLEMENTED_AWAITING_GATES**

## Objective

Introduce a closed, deterministic T0..T4 security classification for semantic Microsoft 365 operations without weakening any policy decision established by CORE-031.

## Model

The canonical `m365_mcp.security_tiers.SecurityTier` is ordered from least to most sensitive:

- `T0` — local/product metadata reads with no authenticated tenant content;
- `T1` — session/runtime/account-context observation or interaction;
- `T2` — authenticated Microsoft 365 content reads;
- `T3` — bounded or reversible mutations;
- `T4` — destructive, externally visible, high-impact, or unclassified risk.

Classification uses only canonical `ToolDefinition` metadata. Mutation class dominates read-risk metadata. Unknown risk classes fail closed to `T4` so a future semantic risk vocabulary cannot silently inherit a lower tier.

## Policy integration

`PolicyResult` now carries the resolved `security_tier`. Existing mutation disablement remains authoritative. A T3/T4 result can only make policy stricter: when mutation execution is not already denied, the operation requires approval.

Unregistered tools remain denied and are not assigned an invented tier.

## Compatibility and boundaries

- all 17 current Planner public tools remain registered and preserve their names/contracts;
- no public mutation is enabled;
- no Outlook tool or capability is activated;
- no session/browser secret or tenant-content field is added;
- resource/account/mailbox scope remains CORE-033;
- per-node BATCH/DAG/RUNBOOK policy remains CORE-034.

## Acceptance coverage

Tests prove stable T0..T4 ordering, risk-class mapping, mutation dominance, fail-closed unknown-risk behavior, policy projection, and denial of unregistered tools without fabricated classification.
