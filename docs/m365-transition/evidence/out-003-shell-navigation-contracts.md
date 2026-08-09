# OUT-003 — Outlook shell/navigation contracts

Status: **INTEGRATED_CLEAN_ON_MAIN**

## Objective

Define the bounded semantic Outlook shell/navigation contract before locator discovery, without embedding a generic browser primitive or making a live-support claim.

## Contract vocabulary

The Outlook application now declares five closed shell targets:

- mail;
- calendar;
- people;
- To Do;
- settings.

Each target has a stable `outlook.shell.*` contract key, a semantic role and an explicit `UNVERIFIED_LIVE` evidence state.

## Deliberate separation from locator evidence

OUT-003 specifies *what* later discovery must identify. It does not specify CSS, XPath, URL, JavaScript, DOM commands or arbitrary browser actions. Locator strategies and UIContract attestation remain evidence-backed work in later Outlook discovery/capability phases.

The model refuses any OUT-003 contract that attempts to claim `ATTESTED` or another live state.

## Safety and dependency boundary

This work is stacked on OUT-002 and cannot merge before OUT-002 is merged and post-merge GREEN. Outlook remains `RESERVED` with zero public Tool Registry entries and zero browser operations.

## Acceptance coverage

Tests prove deterministic target order, namespace uniqueness, authenticated-shell requirement, `UNVERIFIED_LIVE` state, absence of generic browser/session primitives and continued zero Outlook execution exposure.

## Integration reconciliation

The delta is integrated in `main` (clean branch rebased on GREEN `main` and merged through PR #293). Mandatory CI gates (compile/lint/type/contracts/tests, image build + Trivy + SBOM, filesystem/dependency/secret scanning) were GREEN on the merged PR and the post-merge `main` gate set was re-executed locally at `12b363c`.

This records mock-mode integration only. No live Microsoft tenant was contacted, no Outlook capability is promoted to SUPPORTED, the Outlook application stays RESERVED with no public `outlook_*` MCP tool, and the Planner public tool ABI is unchanged.
