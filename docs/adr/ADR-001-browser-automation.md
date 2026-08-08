# ADR-001 — Browser automation as the primary control surface

- Status: Accepted
- Date: 2026-08-08
- Context version: 0.1.0

## Context

Microsoft Planner Premium exposes project-management semantics through its user interface that may
not be consistently available through a single programmatic API. The product requirement is to
support the Planner Premium capability actually available in the target tenant, subject to UI
evidence and safe operation, rather than cap the MCP to Microsoft Graph coverage.

## Decision

The primary Planner implementation path is a **private Chromium instance driven by Playwright**
inside the dedicated browser worker.

A capability can be considered for support only when:

1. it exists in Planner Premium;
2. it is available in the target tenant/licence;
3. it is observable/operable through the UI;
4. its UIContract fragment is validated/attested as required;
5. execution is deterministic enough for the operation class;
6. the result can be read back and verified.

The public MCP exposes only **semantic project-management tools**. Generic browser primitives such
as arbitrary click/type/navigate/evaluate are internal implementation details and are never public
MCP tools.

Microsoft Graph may be added later as an auxiliary optimization behind an already-defined semantic
capability, but it is never a prerequisite or functional gate (ADR-008).

## Consequences

Benefits:

- Planner Premium UI capability, not API coverage, defines the potential product ceiling;
- the client sees a stable semantic contract rather than fragile selectors;
- read-back can prove what the same UI actually shows after an operation.

Costs/risks and controls:

- UI change/fragility → centralized, versioned, attested UIContract and fail-closed drift handling
  (ADR-006);
- browser/session sensitivity → separate control-plane/worker trust boundary (ADR-002) and dedicated
  professional-profile/privacy boundary (ADR-007);
- no browser transaction semantics → reconciliation-first, idempotency, locks, sagas/checkpoints and
  mandatory read-back (ADR-003);
- lower throughput than a direct API → accepted in favor of correctness, evidence and capability
  coverage.

## Rejected alternatives

- **Graph-first with browser fallback** — rejected because it makes Graph availability the practical
  capability gate, contrary to ADR-008.
- **Generic computer-use/browser MCP** — rejected because it exposes arbitrary, weakly governed
  tenant control and loses semantic/audit meaning.
- **Selectors embedded across tools** — rejected because UI change would become uncontrolled and
  difficult to attest; selectors belong to ADR-006/UIContract.

## Release boundary

0.1.0 remains read-only with exactly the canonical 17 `READ` tools. This ADR chooses the execution
surface; it does not authorize write capability.

## Related

ADR-002, ADR-003, ADR-006, ADR-007, ADR-008;
[`browser-worker.md`](../browser-worker.md), [`ui-contract.md`](../ui-contract.md),
[`planner-premium-capabilities.md`](../planner-premium-capabilities.md).
