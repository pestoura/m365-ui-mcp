# OUT-002 — Outlook mock UI/test fixture foundation

Status: **IMPLEMENTED_AWAITING_CURRENT_BASE_GATES**

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

OUT-001, PLN-MIG-001, PLN-MIG-002 and CORE-035 are merged and post-merge GREEN on current `main`. This revision deliberately re-triggers OUT-002 so the complete mandatory suite executes against that cross-lane integration base; earlier GREEN evidence is not reused for merge.
