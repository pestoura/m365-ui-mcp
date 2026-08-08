# ADR-006 — Microsoft Graph is contextual, never a functional gate

- Status: Accepted
- Date: 2026-08-08

## Context

It is tempting to decide "is this capability supported?" by asking whether Microsoft Graph exposes
an endpoint for it. Graph's coverage of Planner Premium semantics is partial and moves
independently of the product UI. Using it as the gate would mean the MCP silently refuses
capabilities the tenant demonstrably has, and would tie the product's roadmap to an API surface
we do not control.

## Decision

**Graph availability does not determine support.** It is contextual information only.

- Support is decided by **observed browser evidence**: the capability exists in the tenant UI, its
  selectors are attested, a deterministic operation is possible, and the result can be **read
  back**.
- No code path may branch on "Graph supports X" to enable or disable a capability.
- No documentation may cite a Graph endpoint as proof that a capability is or is not supported.
- Graph may be referenced in notes as background, clearly labelled as non-authoritative.
- If Graph is ever used at all (it is not in 0.1.0), it would be an optimisation behind an
  already-attested capability, never the definition of one — and its absence must degrade
  performance, not availability.

## Consequences

- The capability matrix's `support_level` column is driven solely by attestation states
  (`UI_ATTESTED` → `READ_ATTESTED` → `MUTATION_ATTESTED` → `SUPPORTED`).
- Premium areas without Graph coverage (WBS detail, dependency types, critical path, formatting
  rules, sprints) are first-class targets rather than permanent gaps.
- The cost is that every capability requires human attestation work. Accepted: that work also
  produces the evidence the governance model requires.
- Correspondingly, a Graph endpoint existing is **not** an excuse to skip attestation.

## Enforcement

- Review rule: any PR gating behaviour on Graph availability is rejected.
- Capability matrix explicitly states this rule at the top of the document.
- `planner_license_capabilities` reports **observed UI** capabilities only.

## Related

[docs/planner-premium-capabilities.md](../planner-premium-capabilities.md),
[docs/vision.md](../vision.md); ADR-001, ADR-007; backlog P-024.
