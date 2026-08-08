# ADR-002 — Control plane / browser worker separation

- Status: Accepted
- Date: 2026-08-08

## Context

The component that holds the authenticated professional browser profile is a high-value trust zone.
The component that accepts MCP client requests is externally exposed by comparison. Combining both
would let a protocol/application flaw reach the browser session directly and would co-locate policy
with arbitrary execution capability.

## Decision

Use two separate components/trust boundaries.

### `planner-mcp` control plane

Owns:

- MCP runtime and semantic tool registry;
- contracts/manifests;
- policy and approvals;
- desired-state/reconciliation orchestration;
- idempotency, locks, sagas/checkpoints;
- persistent state/audit;
- capability/UIContract metadata;
- observability/reporting orchestration;
- calls to the browser worker.

It does **not** mount or directly manipulate the Chromium professional profile.

### `planner-browser-worker`

Owns:

- Playwright/Chromium lifecycle;
- dedicated professional profile;
- browser authentication observation;
- UIContract selector resolution;
- semantic UI reads/actions requested through a closed typed operation contract;
- read-back of UI state.

It does not own policy/approval state, does not expose generic browser primitives to the public MCP
and has no public route.

The worker accepts only schema-valid typed operation envelopes. Unknown operations fail closed.

## Consequences

- external MCP compromise has a narrower path to the browser session;
- policy/governance logic can be tested without a live browser;
- browser/UI logic can be tested against mock surfaces without weakening control-plane policy;
- the worker can restart independently while preserving the dedicated profile volume;
- an explicit internal contract/version must be maintained between components;
- operation correlation/evidence must span both components.

## Enforcement

- worker publishes no public/host port in the production topology;
- control plane does not mount the browser profile volume;
- worker does not mount host home, Docker socket, personal credential directories or Hermes state;
- generic browser actions are not part of the public MCP tool catalogue;
- container/network posture is tested in isolated acceptance;
- dedicated professional-profile handling follows ADR-007.

## Related

ADR-001, ADR-006, ADR-007;
[`architecture.md`](../architecture.md), [`browser-worker.md`](../browser-worker.md),
[`deployment.md`](../deployment.md); backlog P-011, P-013, P-064.
