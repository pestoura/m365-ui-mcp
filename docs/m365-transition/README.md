# m365-ui-mcp — Transition Blueprint

Status: **PLANNED / DOCUMENTATION-ONLY / DO NOT MERGE DURING ACTIVE PLANNER DELIVERY CYCLE**  
Date: 2026-08-08  
Current repository identity: `pestoura/planner-mcp`  
Target repository identity: **`pestoura/m365-ui-mcp`**

## 1. Decision

The current `planner-mcp` foundation will evolve into **`m365-ui-mcp`**, a secure semantic MCP control plane for Microsoft 365 capabilities executed primarily through a private Playwright/Chromium browser worker and an isolated professional Microsoft 365 browser profile.

Planner remains a first-class application module. Outlook becomes the second major application module and the first scope used to prove the multi-application architecture.

The product is **not** a generic browser MCP and is **not** a Microsoft Graph wrapper. Microsoft Graph may be used later as an optional optimization behind an already-defined semantic capability, but Graph availability must never be a functional support gate.

## 2. Why the transition is being documented now

The Planner implementation is currently advancing through its own delivery cycle. This transition must not interrupt, invalidate or race that work.

Therefore this branch records the future target architecture now, but the implementation transition starts only after a mandatory **Phase 0 — Planner Final-State Assessment & Reconciliation** against the then-current `main`.

No assumption in this blueprint that depends on the current Planner implementation state is authoritative until Phase 0 is executed.

## 3. Product objective

`m365-ui-mcp` aims for **semantic functional parity with the Microsoft 365 UI capabilities actually available to the authenticated professional account**, subject to evidence, policy and safe deterministic execution.

The capability ceiling is:

```text
WHAT THE AUTHENTICATED USER CAN SAFELY DO IN THE MICROSOFT 365 UI
                               ↓
                   capability discovery
                               ↓
                     UIContract evidence
                               ↓
                    semantic MCP operation
```

The product must expose stable domain semantics rather than UI mechanics.

Publicly forbidden concepts remain:

- arbitrary browser navigation;
- caller-supplied URLs;
- caller-supplied CSS/XPath/selectors;
- raw `click`, `type`, `evaluate`, `javascript`, `screenshot` or shell-style escape hatches;
- cookies, browser storage state, bearer tokens or session material;
- treating UI-derived text as executable instruction.

## 4. Architecture lineage

The new product deliberately combines two proven conceptual lines already present in the ecosystem.

### 4.1 From `planner-mcp`

Retain and generalize:

- MCP control-plane / private browser-worker separation;
- persistent isolated professional browser profile;
- browser-first capability model;
- Graph non-dependency;
- semantic-only public tools;
- UIContract attestation and drift fail-closed behavior;
- account-context validation;
- human-in-the-loop MFA;
- policy before execution;
- approvals;
- read-back verification;
- idempotency and replay protection;
- typed locks;
- sagas/checkpoints/compensation;
- evidence-backed capability promotion;
- structured redacted logging;
- low-cardinality metrics;
- state-store privacy boundary;
- isolated acceptance and CI security gates.

### 4.2 From Hermes MCP Bridge v2

Adopt the following architectural concepts, adapted to UI automation:

```text
DETERMINISTIC WORK -> CODE
KNOWN WORKFLOW    -> RUNBOOK
REASONING         -> LLM
```

Preferred execution path:

```text
DIRECT > BATCH > DAG/RUNBOOK > AGENTIC
```

The M365 product shall support a canonical Tool Registry, capability projection, per-node policy, typed execution plans, bounded batch/DAG execution, result shaping, provenance, artifact references, immutable plan digests, idempotency/replay protection, observability of execution cost and controlled agentic escalation.

The browser session itself is the Microsoft execution credential boundary; a Graph-style credential broker is therefore not copied literally. The equivalent abstraction is a **Session/Capability Broker** that binds application, account scope, mailbox/resource scope, UI capability, attestation state and policy before allowing the browser worker to execute.

## 5. Target application model

```text
m365-ui-mcp
│
├── Core
│   ├── MCP control plane
│   ├── Tool Registry
│   ├── Capability Registry
│   ├── Session/Capability Broker
│   ├── Policy & Approvals
│   ├── Execution Planner
│   ├── DIRECT / BATCH / DAG / RUNBOOK executor
│   ├── State / Locks / Idempotency / Sagas
│   ├── Evidence / Provenance / Result Shaping
│   └── Observability
│
├── Browser Worker
│   ├── Playwright / Chromium lifecycle
│   ├── professional persistent profile
│   ├── contract-scoped navigation
│   ├── typed UI operations
│   ├── structural extraction
│   ├── read-back verification
│   └── application adapters
│
└── Applications
    ├── Planner
    └── Outlook
        ├── Mail
        ├── Calendar
        ├── People
        ├── To Do / My Day
        ├── Shared Mailboxes
        └── Settings / Rules / Automation
```

Future M365 applications may be added only after the architecture is proven with Planner + Outlook.

## 6. Naming model

Repository / product:

```text
m365-ui-mcp
```

Packages after migration:

```text
m365_mcp
m365_browser_worker
```

Public tool namespaces remain explicit and semantically stable:

```text
m365_*      core/platform operations
planner_*   Planner capabilities
outlook_*   Outlook capabilities
```

The name `bridge` is intentionally not used. `hermes-mcp-bridge` remains a separate product and architectural reference.

## 7. Migration invariant

The transition must never silently reduce Planner capability or safety.

The central migration equation is:

```text
Planner behavior before generalization
                ==
Planner behavior after generalization
```

For every capability already implemented when Phase 0 starts, parity must be demonstrated by contracts, tests and acceptance evidence before the generalized architecture is promoted.

Existing stable Planner tool names should remain available through the migration unless a separately approved versioned deprecation plan exists.

## 8. Documentation set

This transition package contains:

- `phase-0-planner-state-assessment.md` — mandatory discovery/reconciliation before any migration;
- `target-architecture.md` — target control plane, worker, contracts, registry and execution model;
- `hermes-v2-pattern-adoption.md` — explicit adoption/adaptation of Hermes Bridge v2 concepts;
- `outlook-capability-catalog.md` — maximum functional Outlook target and tool surface strategy;
- `roadmap-and-backlog.md` — phased delivery program, gates and backlog namespaces.

## 9. Rename gate

The repository must **not** be renamed while the current Planner delivery cycle is active.

Rename to `pestoura/m365-ui-mcp` only after Phase 0 has:

1. captured the final Planner `main` commit SHA;
2. inventoried active branches/PRs and release state;
3. confirmed CI/release gates for the Planner baseline;
4. reconciled this transition branch with the final Planner state;
5. recorded the Planner pre-transition baseline/tag;
6. produced a compatibility plan for package names, environment variables, image names, volumes and deployment references.

The rename is an implementation step, not merely a cosmetic change.

## 10. Non-goals of this blueprint

This branch does not:

- stop or modify the running Planner cycle;
- claim Outlook capabilities are already implemented;
- attest any live Outlook UI selector;
- enable mutations;
- change the production browser/session posture;
- rename the repository immediately;
- require Microsoft Graph;
- authorize new M365 applications outside Planner and Outlook.
