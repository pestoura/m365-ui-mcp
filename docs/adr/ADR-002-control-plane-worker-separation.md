# ADR-002 — Control plane / browser worker separation

- Status: Accepted
- Date: 2026-08-08

## Context

The component that holds an authenticated corporate browser session is the highest-value target
in this system. The component that talks to an external MCP client is the most exposed. Putting
both in one process means a protocol-level flaw reaches the tenant session directly, and policy
decisions become co-located with the code that can execute anything.

## Decision

Two processes/containers, two trust zones:

- **planner-mcp control plane (Z1)** — MCP protocol, manifests, policy engine, approvals,
  idempotency, locks, reconciliation, state DB, telemetry. Never touches the browser profile.
- **planner-browser-worker (Z2/Z3)** — owns Chromium and the persistent profile, executes a
  **closed enum** of typed operations, resolves UI contract fragments, returns typed results plus
  evidence hashes. Makes no policy decisions, holds no approval state, has no public route.

The boundary is a one-way command channel: Z1 sends validated operation envelopes; Z2 returns
typed results. Z2 never calls Hermes and is not reachable from the internet or the host network.

## Consequences

- A compromised or buggy MCP surface still cannot issue an arbitrary browser action — only
  operations in the enum, only with schema-valid arguments, only after a policy decision.
- Authorisation logic is testable without a browser; browser logic is testable without policy.
- The worker can be restarted independently; the profile volume preserves the session.
- Costs: an extra hop, envelope schemas to maintain, and correlation via `operation_id`. Accepted.

## Enforcement

- Worker publishes no host ports; `internal: true` network.
- Control plane has no mount of the profile volume.
- Unknown operation ⇒ `UNKNOWN_OPERATION`; schema-invalid ⇒ `SCHEMA_INVALID`.
- Container posture asserted automatically (IA-15).

## Related

ADR-001, ADR-008; [docs/architecture.md](../architecture.md);
[docs/deployment.md](../deployment.md); backlog P-011, P-064.
