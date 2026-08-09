# OUT-002 — Outlook mock UI/test fixture foundation

Status: **INTEGRATED_CLEAN_ON_MAIN**

## Objective

Create a deterministic, tenant-neutral fixture foundation for later Outlook UI-contract and adapter testing without authenticating to Microsoft 365 or activating any Outlook execution surface.

## Implementation

`m365_mcp.apps.outlook.mock_ui` defines a versioned synthetic fixture set containing:

- one opaque synthetic primary-mailbox key;
- bounded synthetic folder keys;
- bounded synthetic message metadata;
- explicit `synthetic=true` provenance;
- deterministic fixture versioning.

The fixture contains no selector, URL, mailbox address, tenant identifier, cookie, token, storage state or copied Microsoft tenant content.

## Dependency and safety boundary

This is a stacked continuation of OUT-001. OUT-003 may use the fixture vocabulary to define shell/navigation contracts, but selectors and live evidence remain separate reviewed concerns.

Outlook remains `RESERVED`:

- no public `outlook_*` tools;
- no worker operation activation;
- no tenant authentication;
- no mutation;
- no live-support claim.

## Acceptance coverage

Tests prove determinism, synthetic provenance, absence of identity/routing/session material, and continued zero Outlook public-tool/browser-operation exposure.

## Integration reconciliation

The delta is integrated in `main` (clean branch rebased on GREEN `main` and merged through PR #292). Mandatory CI gates (compile/lint/type/contracts/tests, image build + Trivy + SBOM, filesystem/dependency/secret scanning) were GREEN on the merged PR and the post-merge `main` gate set was re-executed locally at `12b363c`.

This records mock-mode integration only. No live Microsoft tenant was contacted, no Outlook capability is promoted to SUPPORTED, the Outlook application stays RESERVED with no public `outlook_*` MCP tool, and the Planner public tool ABI is unchanged.
