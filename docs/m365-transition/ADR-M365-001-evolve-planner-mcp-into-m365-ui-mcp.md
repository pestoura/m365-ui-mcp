# ADR-M365-001 — Evolve planner-mcp into m365-ui-mcp

- Status: **Proposed / accepted in product direction, implementation gated by Phase 0**
- Date: 2026-08-08
- Current repository: `pestoura/planner-mcp`
- Target repository: `pestoura/m365-ui-mcp`

## Context

`planner-mcp` was created as a secure semantic MCP for Microsoft Planner Premium using a private Playwright/Chromium browser worker and an isolated professional browser profile. The architecture already contains a large amount of application-neutral safety infrastructure: control-plane/worker separation, policy, contracts, capabilities, UI attestation, evidence, state, approvals, locks, idempotency, sagas/checkpoints, read-back and observability.

The product requirement has expanded to Outlook Web with an explicit objective of maximum practical functional coverage, including mail, categories, flags/follow-up, folders, rules, Quick Steps, conditional formatting, calendar, scheduling, People, To Do, shared mailboxes, settings, security controls and composite cross-application workflows.

Creating a separate `outlook-mcp` by copying Planner would duplicate the highest-risk and most expensive infrastructure and would create competing browser/session ownership models.

The Hermes MCP Bridge v2 design also establishes useful execution principles: deterministic-first routing, canonical tool registry, capability projection, DIRECT/BATCH/DAG/RUNBOOK execution, per-node policy, immutable plan digests, result shaping, provenance and controlled agentic fallback.

## Decision

Evolve the current repository and architecture into **`m365-ui-mcp`**.

The change is a controlled generalization, not a rewrite.

The product will:

1. retain Playwright/Chromium as the primary functional backend;
2. retain Microsoft Graph as an optional non-gating optimization only;
3. retain one isolated professional browser profile as the authentication boundary initially;
4. generalize the control plane and browser worker into M365 core components;
5. move Planner into a first-class application adapter while preserving stable `planner_*` public semantics;
6. add Outlook as the second application adapter;
7. introduce `m365_*` core/composite tools and `outlook_*` Outlook semantic tools;
8. adopt the relevant Hermes v2 deterministic execution concepts without making Hermes or its LLM a mandatory hop;
9. require a final-state assessment of Planner before any implementation transition or repository rename;
10. preserve or strengthen all current Planner security/governance controls.

## Repository rename

The intended rename is:

```text
pestoura/planner-mcp
-> pestoura/m365-ui-mcp
```

The rename is delayed until the active Planner delivery cycle completes and Phase 0 records/reconciles the final state.

## Public compatibility

Existing Planner public tool names are not renamed merely because the repository changes name.

```text
planner_* -> preserved
outlook_* -> new
m365_*    -> new platform/cross-app surface
```

Configuration and package names may migrate with versioned compatibility aliases according to the transition plan.

## Core execution model

```text
DETERMINISTIC WORK -> CODE
KNOWN WORKFLOW    -> RUNBOOK
REASONING         -> LLM
```

Preferred path:

```text
DIRECT > BATCH > DAG/RUNBOOK > AGENTIC
```

Known M365 UI operations must not require an intermediate LLM to perform already-defined browser actions.

## Security boundary

The browser worker remains a high-value trust zone.

The control plane:

- never receives browser cookies/tokens/storage state;
- never launches or controls Chromium directly;
- never exposes raw browser primitives;
- authorizes semantic operations before worker execution.

The worker:

- holds the persistent profile;
- executes only closed typed operations;
- resolves its own attested UI contracts;
- performs structural extraction/read-back;
- never becomes publicly addressable.

## UIContract decision

Move from a single global Planner UIContract availability state toward application/surface/capability-scoped contract fragments.

UI drift in one Outlook setting must not disable unrelated Planner or Outlook reads.

## Capability decision

Capabilities become scoped by application, surface and resource/mailbox/account context. Registration does not imply current availability.

Support remains evidence-driven.

## Policy decision

Move from static tool-name policy lists toward registry-metadata-driven policy with explicit mutation/risk/security classes.

Every BATCH/DAG/RUNBOOK child node is governed independently.

## Read-back decision

Mandatory read-back remains a product invariant for all UI mutations.

No mutation is successful merely because an interaction completed.

## State/privacy decision

The generalized state store remains control metadata, not a mirror of Microsoft 365 data. Mail bodies, attachments, recipient lists, contact data and calendar content are not persisted by default.

## Hermes relationship

`hermes-mcp-bridge` remains a separate repository/product.

Its v2 architecture is a reference pattern, not a parent runtime dependency.

Hermes may later provide approvals, notifications, cross-system orchestration or controlled reasoning escalation, but deterministic M365 execution should be callable directly through `m365-ui-mcp`.

## Rejected alternatives

### Separate `outlook-mcp`

Rejected because it duplicates control plane, worker, session, policy, state, observability and security infrastructure, and creates competing ownership of the same professional browser session.

### Keep repository named `planner-mcp` and add Outlook

Rejected because product identity would no longer match scope and future architecture/documentation would remain artificially Planner-centric.

### `mcp365-bridge` / `m365-bridge`

Rejected to avoid confusion with the existing Hermes bridge and because this product is itself an MCP semantic execution product rather than merely a bridge.

### Graph-first M365 MCP

Rejected as the primary model because the product requirement is based on the capabilities available in the Microsoft 365 UI, not solely on Graph coverage/permissions.

### Generic computer-use/browser MCP

Rejected because it would expose arbitrary UI execution, weaken audit/policy semantics and increase session risk.

## Consequences

Benefits:

- reuse of existing hardened Planner foundation;
- one browser/session ownership model;
- one governance/evidence architecture;
- shared Outlook + Planner orchestration;
- lower duplication and maintenance burden;
- direct deterministic execution reduces unnecessary LLM hops/tokens;
- future M365 apps have a defined adapter model.

Costs:

- early refactor/generalization required;
- compatibility layer required during naming/package migration;
- larger capability and contract registry;
- Outlook content introduces stronger privacy/data-minimization requirements;
- UI fragmentation and capability projection become more sophisticated;
- browser-profile concurrency remains a throughput constraint until safely redesigned.

## Implementation gate

This ADR does not authorize immediate code changes while the current Planner cycle is active.

Implementation starts only after `M365-SETUP-001..010` are complete and the transition blueprint has been reconciled against the final Planner `main`.
