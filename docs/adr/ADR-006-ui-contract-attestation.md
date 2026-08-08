# ADR-006 — Centralized UI contract with attestation

- Status: Accepted
- Date: 2026-08-08

## Context

Selectors scattered through automation code are a primary failure mode of browser agents: they rot silently, become duplicated with subtle differences, are invented from guesswork, and can cause an agent to perform the wrong operation after a UI change. Against a corporate project-management tool, that can affect real project state.

## Decision

1. **One contract.** Every selector, wait condition and extraction rule lives in `src/planner_mcp/browser/selectors/`. No selector may appear elsewhere in executable browser code; CI must enforce this boundary.
2. **Evidence before use.** A fragment starts `UNVERIFIED_LIVE` and can only advance from a recorded observation of the live Planner Premium UI. A fragment that is not attested cannot be used by an operation that depends on it.
3. **Attestation with evidence.** Advancing a fragment records operator/context metadata, locale/UI version where available, structural/evidence hashes, validation time, expiry and confidence. Sensitive artifacts remain local; only sanitized metadata and hashes may be committed.
4. **Semantic selector preference.** Prefer role, accessible name, semantic text and stable data attributes. Structural selectors are a last resort. Volatile CSS classes and `nth-child`-style selectors are prohibited unless explicitly attested as a constrained exception.
5. **Drift fails closed.** Required anchors and structural expectations are verified before use. A mismatch yields `UI_DRIFT` / `BLOCKER_UI_DRIFT`; affected operations refuse rather than clicking or probing arbitrarily during a mutation.
6. **Versioned.** The UIContract has its own semantic version and is pinned for the duration of an operation/reconciliation run.
7. **Read-back is part of support.** A capability is not supportable merely because a control can be located; deterministic execution plus a validated read-back strategy are required.

## Consequences

- Availability is deliberately traded for safety: a Microsoft UI change stops the affected capability instead of silently changing behaviour.
- Recovery requires re-observation and re-attestation plus a new contract version where the contract changes.
- Mock UI tests prove refusal, drift and fallback boundaries, but mock evidence never promotes a live capability state.
- Capability support remains evidence-driven and independent from Microsoft Graph availability.

## Enforcement

- CI rejects selector/navigation primitives outside the selector/contract boundary.
- Capability registry entries reference the exact UIContract fragment and attestation state.
- Mutation code may never perform exploratory clicks after contract validation fails.

## Related

[docs/ui-contract.md](../ui-contract.md), [docs/browser-worker.md](../browser-worker.md),
[docs/planner-premium-capabilities.md](../planner-premium-capabilities.md),
[docs/vision.md](../vision.md); backlog P-014, P-015, P-016, P-017.
