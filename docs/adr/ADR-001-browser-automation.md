# ADR-001 — Browser automation as the primary control surface

- Status: Accepted
- Date: 2026-08-08
- Context version: 0.1.0

## Context

Microsoft Planner Premium (Project for the web) exposes rich project semantics in its UI — WBS,
dependency types, scheduling, goals, sprints, portfolios. The programmatic surfaces available to
us do not cover that semantic space consistently, and their coverage changes without notice.
Building the product on an API subset would permanently cap what the MCP can do, regardless of
what the tenant actually offers.

## Decision

The primary control surface is a **private Chromium instance driven by Playwright** inside a
dedicated worker. All tenant reads and mutations go through that surface. A capability is
supportable if it is present in the tenant UI and can be operated deterministically **and read
back**.

The public MCP surface exposes **semantic project tools only** (`planner_task_list`,
`planner_dependency_add`). Raw navigation primitives (`click`, `type`, `goto`, arbitrary
`evaluate`) are internal to the worker and are never exposed as MCP tools.

## Consequences

Positive: capability ceiling is the product itself, not an API subset; the same mechanism serves
every Premium area; behaviour matches what a human sees.

Negative / mitigations:
- Fragility to UI change ⇒ centralized UIContract with attestation and fail-closed drift handling
  (ADR-007).
- Non-determinism ⇒ no fixed sleeps, attested anchors only, deadlines, single-writer profile.
- No transactions ⇒ read-back, idempotency classes and sagas (ADR-003).
- Session material on the host ⇒ trust-zone separation (ADR-002) and privacy boundary (ADR-008).
- Slower than an API ⇒ accepted; correctness and coverage outrank latency.

## Rejected alternatives

- **Graph-first with browser fallback** — makes Graph the de facto gate and hides capability
  behind whichever surface is easier; rejected (ADR-006).
- **Generic "computer use" agent** — non-deterministic, unauditable, unsafe against a corporate
  tenant.
- **Exposing browser primitives as MCP tools** — hands arbitrary tenant control to the client with
  no policy, no read-back and no audit meaning.

## Related

ADR-002, ADR-003, ADR-006, ADR-007; [docs/browser-worker.md](../browser-worker.md);
[docs/ui-contract.md](../ui-contract.md).
