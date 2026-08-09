# Release maintenance governance

`m365-ui-mcp` adopts JDS-002 for post-baseline change, validation and release maintenance governance.

## Product invariants

- Planner and Outlook support states remain independent.
- Mock/synthetic implementation never implies live Microsoft 365 support.
- Outlook remains `RESERVED / LIVE UNOBSERVED` with zero public Outlook tools until live UI evidence promotes a semantic capability.
- Microsoft Graph availability is not a functional promotion gate.
- Public MCP semantics remain separate from private Playwright/UI implementation details.
- A merged wave does not imply execution-index acceptance, public registry promotion or live tenant support.
- A functional correction discovered after candidate evidence requires a new candidate/release identity.
- Non-blocking improvements may be deferred rather than extending the current validation campaign indefinitely.

## Change flow

```text
wave/candidate
  -> validation campaign
  -> observation
  -> CHG-M365-* when remediation is required
  -> bounded implementation lane
  -> product-specific CI/JDS/UI-contract gates
  -> revalidation
  -> controller/index reconciliation
  -> candidate/release promotion
  -> live UI attestation where applicable
```

JDS-002 governs the transversal record lifecycle. The M365 execution index, UIContract/read-back evidence, policy, approval and application-specific acceptance remain authoritative for product support.
