# OUT-001 — Outlook application module skeleton

Status: **INTEGRATED_CLEAN_ON_MAIN**

## Objective

Create the application-owned Outlook package boundary without activating any Outlook tool, capability, browser operation or tenant mutation.

## Implementation

`m365_mcp.apps.outlook` now contains an inert foundation manifest. It is deliberately aligned with the closed Application Registry:

- application key: `outlook`;
- state: `RESERVED`;
- capability namespace: `outlook`;
- public tools enabled: false;
- browser operations enabled: false.

The package exports no registrar. The existing Application Registry remains the execution authority and continues to reject a registrar for a RESERVED application.

## Safety and compatibility

- all existing Planner registrations remain unchanged;
- the canonical Tool Registry still contains zero `outlook_*` public tools;
- no selectors, URLs, generic browser primitives, session secrets or tenant content are introduced;
- OUT-002+ discovery/mock work can build behind this boundary without prematurely enabling Outlook.

## Acceptance coverage

Tests prove that the new application-owned manifest agrees with the closed registry and that Outlook still has no public Tool Registry or browser execution surface.

## Integration reconciliation

The delta is integrated in `main` (merged before the clean-rebase campaign). Mandatory CI gates (compile/lint/type/contracts/tests, image build + Trivy + SBOM, filesystem/dependency/secret scanning) were GREEN on the merged PR and the post-merge `main` gate set was re-executed locally at `12b363c`.

This records mock-mode integration only. No live Microsoft tenant was contacted, no Outlook capability is promoted to SUPPORTED, the Outlook application stays RESERVED with no public `outlook_*` MCP tool, and the Planner public tool ABI is unchanged.
