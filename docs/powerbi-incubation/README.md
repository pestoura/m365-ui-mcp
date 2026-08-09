# Power BI UI MCP — Incubation Blueprint

Status: **INCUBATION / VNEXT INPUT**

Target standalone repository: `pestoura/powerbi-ui-mcp` (to be created when repository-creation capability is available).

Target long-term destination: integration into a future major/minor evolution of `pestoura/m365-ui-mcp` after the current Planner + Outlook M365 transition reaches its acceptance baseline.

## Purpose

Preserve and formalize the Power BI design decisions discussed during the M365 UI MCP program before implementation starts.

The Power BI module is not intended to depend on Microsoft Graph, Dataverse, Power BI REST APIs or an Azure App Registration as mandatory functional backends. The primary execution path is an authenticated Microsoft 365 browser session controlled by a dedicated Playwright/Chromium worker.

Where Power BI exposes developer surfaces inside the product UI, the implementation should prefer those higher-level mechanisms over repetitive GUI interaction. The intended execution hierarchy is:

1. TMDL / model code surfaces when available;
2. DAX editor for measures, calculated columns/tables and model logic;
3. Power Query M / Advanced Editor where available;
4. semantic DOM / ARIA Playwright automation;
5. keyboard and clipboard acceleration;
6. geometry-aware canvas interaction;
7. vision-assisted recovery/validation;
8. absolute coordinates only as a last-resort fallback.

## Core architecture

```text
ChatGPT / Codex
      |
      v
m365-ui-mcp control plane
      |
      +-- planner worker  -> isolated Chromium/profile
      +-- outlook worker  -> isolated Chromium/profile
      +-- powerbi worker  -> isolated Chromium/profile
                              |
                              +-- Power BI Service
                              +-- semantic UI automation
                              +-- TMDL / DAX / M fast paths
                              +-- visual/canvas engine
                              +-- evidence + validation
```

The Power BI browser worker must be isolated from Planner and Outlook workers at process/container, profile, state, evidence and logging level.

## Authentication model

Authentication remains human-in-the-loop for MFA.

Expected flow:

```text
worker starts
  -> navigate to Power BI
  -> Microsoft sign-in
  -> username/password obtained locally from approved secret storage
  -> detect Authenticator number-matching challenge
  -> send challenge number to the user's Telegram through Hermes
  -> user confirms the displayed number in Microsoft Authenticator
  -> worker observes successful authentication
  -> persist bounded session state/profile
  -> continue Power BI operation
```

Credentials must not be passed through ChatGPT prompts, MCP tool arguments, logs or screenshots.

Conditional Access, device-compliance requirements, ambiguous MFA state or other tenant controls are blockers and must not be bypassed.

## Product objective

The objective is not a generic click-bot. The objective is a semantic Power BI domain automation layer capable of executing high-level operations such as:

- inspect a workspace/report/model;
- create and modify pages;
- create, configure, position and format visuals;
- manage filters, slicers, interactions, bookmarks and navigation;
- create and modify DAX measures;
- edit supported semantic model objects;
- use TMDL for bulk/model-level edits where exposed;
- use Power Query M for query transformations where exposed;
- refresh and validate report/model state through the UI;
- capture evidence for every mutation;
- detect UI drift and fail closed when state cannot be attested.

## First real acceptance target

The initial read-only target is the existing Power BI report discussed during design:

- workspace id: `3ae2d9a3-b405-4152-a1c8-879a7ccb21d3`
- report id: `7acf5f37-10ba-470b-935f-c41b72cd58c8`
- page id: `eed2ea3adc9cb7d90157`

No credential, tenant secret or authentication material is stored in this repository.

## Integration rule

Do not merge Power BI implementation into the active M365 program prematurely.

The intended sequence is:

```text
current m365-ui-mcp Planner/Outlook program
        -> acceptance baseline GREEN
        -> freeze/version baseline
        -> create Power BI integration version
        -> import/reconcile this incubation blueprint
        -> capability discovery against live tenant
        -> implement Power BI worker/module in gated phases
```

Power BI backlog IDs use the namespace `PBI-*` and must not reuse or renumber existing Planner, Outlook, CORE, XAPP or REL identifiers.
