# ADR-008 — Microsoft Graph API is a non-dependency and never a functional gate

- Status: Accepted
- Date: 2026-08-08

## Context

The Planner MCP is designed around the capabilities actually available in Microsoft Planner Premium in the target tenant. Microsoft Graph coverage of Planner Premium semantics is incomplete and evolves independently of the product UI. Using Graph availability as a support gate would silently exclude capabilities that are visibly available and operable through the Planner Premium UI.

## Decision

**Microsoft Graph is not a dependency of the Planner MCP capability model and never determines whether a capability is supported.**

Support is decided from browser evidence:

1. the capability exists in Planner Premium;
2. it is available in the tenant/licence in use;
3. it is observable/operable through the UI;
4. the corresponding UIContract fragment is validated and attested;
5. the operation can execute deterministically;
6. the result can be read back and verified.

No code path may enable or disable a capability merely because Graph exposes or does not expose an endpoint for it. Documentation must not cite Graph availability as evidence that a Planner Premium capability is supported or unsupported.

Graph may be introduced later only as an auxiliary implementation or optimisation behind an already-supported semantic capability. Its absence must not remove a capability that remains safely available through the browser implementation.

## Consequences

- Premium areas without Graph coverage remain first-class roadmap targets.
- Every capability requires browser/UI evidence and attestation.
- `planner_license_capabilities` and `planner_capabilities` report observed/evidenced capability state, not marketing documentation or Graph coverage.
- Any future Graph adapter remains optional and replaceable behind the same semantic tool contract.

## Enforcement

- Architecture/review rule: reject changes that use Graph availability as a capability gate.
- Capability matrix contains no decisive Graph-availability column.
- Tests must prove that capability support state is derived from evidence/attestation, not Graph metadata.

## Related

[docs/planner-premium-capabilities.md](../planner-premium-capabilities.md),
[docs/architecture.md](../architecture.md), [docs/vision.md](../vision.md);
ADR-001, ADR-006; backlog P-024.
