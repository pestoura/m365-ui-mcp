# CORE-041 — Compensation registry

Status: **INTEGRATED_ON_MAIN**

## Objective

Require every registered mutation to declare explicitly whether compensation is automatic, manual-only or unavailable and bind that declaration to the exact semantic tool version and mutation class.

## Closed compensation vocabulary

`CompensationAvailability`:

```text
AUTOMATIC
MANUAL_ONLY
UNAVAILABLE
```

`CompensationStrategy`:

```text
DELETE_CREATED_RESOURCE
RESTORE_PREVIOUS_STATE
INVERSE_OPERATION
MANUAL_RECONCILIATION
NONE
```

Availability and strategy combinations are validated fail-closed:

- `AUTOMATIC` requires one of the three automatic strategies;
- `MANUAL_ONLY` requires `MANUAL_RECONCILIATION`;
- `UNAVAILABLE` requires `NONE`;
- read-only tools cannot declare compensation.

## Exact mutation binding

Each `CompensationDefinition` binds:

- semantic tool name;
- exact tool version;
- exact `MutationClass`;
- availability;
- strategy;
- whether an execution checkpoint is required.

`CompensationRegistry.for_tool()` refuses missing definitions and mutation-class drift. `validate_tool_registry_coverage()` requires every mutating Tool Registry entry to have one exact compensation definition and rejects orphan definitions left behind by tool removal/rename/version drift.

## Current 0.1.0 state

The current public Tool Registry contains exactly 17 preserved Planner tools and all are `MutationClass.READ`. Public mutations remain disabled. Therefore the canonical current compensation registry is deliberately empty and coverage validation succeeds only because there are no registered mutations.

This is not an implicit `NONE` assumption: as soon as a mutation is registered, an empty registry fails the coverage gate and that mutation cannot be considered compensation-governed until an explicit definition exists.

## Relationship to adjacent CORE phases

- CORE-040 owns the generalized execution/checkpoint lifecycle.
- CORE-041 declares compensation availability and strategy only; it does not execute compensation.
- CORE-042 owns the `INDETERMINATE` terminal state for mutations whose resulting Microsoft state cannot be proven.

No compensation strategy can therefore silently manufacture a proven terminal state.

## Security/privacy boundary

The registry contains semantic metadata only. It does not contain tenant content, request/result payloads, Microsoft resource ids, mailbox identities, browser profile paths, cookies, tokens or storage state.

## Acceptance coverage

Tests prove:

- the current read-only Tool Registry has valid explicitly empty compensation coverage;
- any future mutation without a definition fails closed;
- automatic definitions bind exact version/class and expose automatic availability;
- manual-only and unavailable strategies remain distinguishable;
- invalid availability/strategy pairs are rejected;
- read-only tools cannot declare compensation;
- version/class drift fails closed;
- orphan compensation declarations are rejected.

## Current integration gate

CORE-040 is merged and post-merge GREEN on `main` at `2bfa50b2f6c58196f1079e026de0c13b921368fd`. PR #265 is now based directly on that integration point. The CORE-041-specific line-length issue was corrected in advance. This revision deliberately re-triggers the complete mandatory current-base CI/security/image/Trivy/SBOM/documentation suite; stacked evidence is not reused for merge.

## Integration reconciliation

This requirement's delta is present in `main`. The mandatory CI gate set (compile/lint/type/contracts/tests, image build + Trivy + SBOM, filesystem/dependency/secret scanning) was GREEN on the merged pull request, and the full gate set was re-executed on post-merge `main` at `9b4a645`.

Mock mode only: no live Microsoft tenant was contacted, no capability is promoted to SUPPORTED by this record, Outlook stays RESERVED, and the 17-tool Planner public ABI is unchanged.
