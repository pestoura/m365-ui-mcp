# OUT-007 — Outlook readiness/smoke extension

Status: **IMPLEMENTED_ON_CURRENT_MAIN**

## Objective

Provide a sanitized, low-cardinality readiness/smoke projection for the reserved Outlook application, composing existing evidence without promoting live support.

## Model

`m365_mcp.apps.outlook.readiness` introduces a closed readiness state model:

```text
FOUNDATION_READY
DISCOVERY_READY
BLOCKED
REATTESTATION_REQUIRED
```

Inputs are already-sanitized artifacts only:

- OUT-001 inert foundation manifest (`public_tools_enabled` / `browser_operations_enabled` must be false);
- OUT-004 capability discovery candidates;
- OUT-005 primary-mailbox context;
- optional OUT-006 shared-mailbox context.

## Precedence and fail-closed behavior

Re-attestation dominates all other outcomes. An invalid primary context or any blocked candidate yields `BLOCKED`. Only an observed candidate with a valid primary context yields `DISCOVERY_READY`; otherwise the state stays `FOUNDATION_READY`.

The evaluator rejects empty and duplicate candidate sets, and rejects any non-inert Outlook execution surface.

## Projection boundary

`to_dict()` emits only bounded counters, booleans and state, plus explicit negative assertions `live_support_promoted=false`, `public_tools_enabled=false`, `browser_operations_enabled=false`. Digests, mailbox identity, selectors, URLs and session material are never projected.

`DISCOVERY_READY` is an internal evidence statement, not a live-support claim.

## Safety boundary

Outlook remains `RESERVED`. Tests assert Outlook is absent from both the public Tool Registry and the Capability Registry. No browser primitives, no Microsoft Graph dependency, no mutation. The Planner ABI is unchanged.

## Acceptance coverage

`tests/test_outlook_readiness.py` covers foundation-only readiness, bounded read-only discovery readiness, blocked primary context, re-attestation precedence, identity-free shared-context projection, empty/duplicate candidate rejection and public-registry absence.

## Integration base

Implemented directly on `main` after OUT-006 merged via PR #301; no stacked dependency remains.
