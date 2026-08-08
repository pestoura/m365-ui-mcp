# ADR-M365-001 — Evolve planner-mcp into m365-ui-mcp

- Status: **Accepted / CORE-002 rename executed**
- Date: 2026-08-08
- Accepted after Phase 0: 2026-08-08
- Former repository: `pestoura/planner-mcp`
- Current canonical repository: `pestoura/m365-ui-mcp`
- GitHub repository ID: `1327254732`
- Planner compatibility baseline: `planner-pre-m365-0.1.0`

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
9. preserve the immutable pre-transition Planner baseline and its compatibility evidence;
10. preserve or strengthen all current Planner security/governance controls.

## Repository rename

The approved rename has been executed:

```text
pestoura/planner-mcp
-> pestoura/m365-ui-mcp
```

`CORE-002` read-back verified:

- GitHub repository ID remained `1327254732`;
- default branch remained `main`;
- rename-point `main` remained `24da6de7a88e18e7cc6f11b0216d91d602136816`;
- `planner-pre-m365-0.1.0` remained at `232c72632ab5c93d0bee70ac588af08422cbc42d`;
- the former GitHub route resolves to the same renamed repository;
- no repository recreation, force-ref update or content deletion occurred.

The rename operation initially returned a bridge timeout. In accordance with the mutation-reconciliation rule, it was **not retried blindly**. Independent GitHub read-back proved the mutation had landed before any further change was made.

## Public compatibility

Existing Planner public tool names are not renamed merely because the repository changes name.

```text
planner_* -> preserved
outlook_* -> new
m365_*    -> new platform/cross-app surface
```

Configuration and package names migrate only through subsequent versioned compatibility work.

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

## Phase 0 resolution

Phase 0 completed on `main` after PR #213 was reconciled and merged.

The post-Phase-0 state was `17819e0a804753712f6eef3ac1e02e27249c1e00`, with both canonical documentation and full CI/security/image/SBOM workflows completed successfully. The pre-transition Planner implementation remains anchored by `planner-pre-m365-0.1.0` at `232c72632ab5c93d0bee70ac588af08422cbc42d`.

The assessment confirmed that the worker is mock-first and not live-attested; therefore this ADR authorizes the controlled core/product transition, not unsupported claims of live Planner or Outlook capability.

## Implementation gate

`CORE-001` is merged and its post-merge gates are GREEN. `CORE-002` repository identity mutation has landed and is independently read-back verified. Completion of `CORE-002` requires this evidence/documentation PR and its own post-merge gates to remain GREEN before `CORE-003` begins.
