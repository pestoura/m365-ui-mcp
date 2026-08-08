# Planner MCP

Canonical control plane exposing **Microsoft Planner Premium** project-management capability to agents as
**semantic MCP tools**, driven by browser evidence rather than by API availability.

> Status: **A1 — Specification and ADRs**. This repository currently contains design-authoritative
> documentation only. No runtime code, no tenant access, no live capability claims.

## Canonical architecture

```
ChatGPT (or other MCP client)
    -> Cloudflare MCP Server Portal        (edge auth, exposure, policy)
    -> Planner MCP control plane           (semantic tools, policy, state, reconciliation)
    -> private planner-browser-worker      (isolated, non-public, session owner)
    -> Playwright / Chromium               (persistent professional profile)
    -> Microsoft Planner Premium UI        (system of record)
```

Hermes is **out of band**: notifications and human-in-the-loop (HITL) signalling only.
Hermes never performs, approves, relays or proxies MFA. See [ADR-004](docs/adr/ADR-004-human-in-loop-mfa.md).

**Microsoft Graph / public API availability is contextual only and MUST NOT determine support.**
A capability is supported when it is attested in the UI by the worker, not when Graph exposes an endpoint.
See [ADR-006](docs/adr/ADR-006-graph-not-a-functional-gate.md).

## Non-negotiable boundaries

- The operator's machine is a **personal device**. It is never enrolled into Intune, Company Portal,
  Microsoft Identity Broker, Entra device registration, MDM, corporate EDR, or issued device certificates.
  See [docs/privacy-boundary.md](docs/privacy-boundary.md) and [ADR-008](docs/adr/ADR-008-personal-device-privacy-boundary.md).
- If Conditional Access requires a compliant/managed device, the system reports
  `BLOCKER_CONDITIONAL_ACCESS` and stops. There is no bypass and no spoofing path.
- The professional password is never present in the repository, environment variables, MCP payloads,
  Hermes messages, logs, or persisted state.
- MFA number matching is surfaced as a sanitized payload only; approval happens exclusively in
  Microsoft Authenticator by the human.
- The system **fails closed** on UI drift, selector uncertainty, session ambiguity or policy uncertainty.

## Document map

| Area | Document |
|---|---|
| Product intent | [docs/vision.md](docs/vision.md) |
| System design | [docs/architecture.md](docs/architecture.md) |
| Threats | [docs/threat-model.md](docs/threat-model.md) |
| Security controls | [docs/security.md](docs/security.md) |
| Governance & policy | [docs/governance.md](docs/governance.md) |
| Authentication & MFA | [docs/authentication-and-mfa.md](docs/authentication-and-mfa.md) |
| Privacy boundary | [docs/privacy-boundary.md](docs/privacy-boundary.md) |
| Premium capability matrix | [docs/planner-premium-capabilities.md](docs/planner-premium-capabilities.md) |
| Tool catalog | [docs/tool-catalog.md](docs/tool-catalog.md) |
| Reconciliation | [docs/reconciliation.md](docs/reconciliation.md) |
| Idempotency | [docs/idempotency.md](docs/idempotency.md) |
| State model | [docs/state-model.md](docs/state-model.md) |
| UIContract | [docs/ui-contract.md](docs/ui-contract.md) |
| Browser worker | [docs/browser-worker.md](docs/browser-worker.md) |
| Observability | [docs/observability.md](docs/observability.md) |
| Testing | [docs/testing.md](docs/testing.md) |
| Acceptance | [docs/acceptance.md](docs/acceptance.md) |
| Deployment | [docs/deployment.md](docs/deployment.md) |
| Cloudflare MCP Portal | [docs/cloudflare-mcp-portal.md](docs/cloudflare-mcp-portal.md) |
| Hermes integration | [docs/hermes-integration.md](docs/hermes-integration.md) |
| Reporting | [docs/reporting.md](docs/reporting.md) |
| Roadmap | [docs/roadmap.md](docs/roadmap.md) |
| Release process | [docs/release-process.md](docs/release-process.md) |
| Traceability | [docs/traceability.md](docs/traceability.md) |
| Definition of Done | [docs/definition-of-done.md](docs/definition-of-done.md) |
| Decisions | [docs/adr/README.md](docs/adr/README.md) |

## Contracts

Design version **0.1.0**: `CapabilityManifest`, `AgentCard`, `ToolManifest`, `ExtendedToolManifest`,
each carrying `trust_level`, `mutation_class`, `reversible`, `idempotency_class`,
`approval_requirement`, `attestation_status`. Mutation classes: `READ`, `SAFE_WRITE`,
`GOVERNED_WRITE`, `DESTRUCTIVE`. See [docs/tool-catalog.md](docs/tool-catalog.md).

## Provenance

Mature operational patterns are referenced read-only from `pestoura/hermes-mcp-bridge`
(manifest shape, health/readiness split, redaction discipline, structured logging).
Nothing is forked and no secret material is copied. See
[ADR-005](docs/adr/ADR-005-hermes-bridge-patterns-golden-baseline.md).
