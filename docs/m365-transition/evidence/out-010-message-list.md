# OUT-010 — Message list

Status: **INTEGRATED_CLEAN_ON_MAIN**

## Objective

Introduce the first bounded Outlook read model for message listing while keeping execution synthetic-only and Outlook globally `RESERVED` until the foundation/readiness predecessors are integrated and live UI evidence exists.

## Semantic model

`m365_mcp.apps.outlook.message_list` defines:

- `MessageListRequest` with semantic `folder_key`, non-negative offset and page limit 1..100;
- `MessageListItem` with opaque message key plus minimal list metadata;
- `MessageListResult` with deterministic pagination metadata and explicit synthetic provenance.

The current executor is `list_fixture_messages()`. It consumes only the tenant-neutral OUT-002 fixture and requires an OUT-007 report whose `ready_for_readonly_discovery` property is true.

## Fail-closed rules

- non-synthetic fixtures are rejected;
- readiness below `DISCOVERY_READY` is rejected;
- unknown fixture folder keys are rejected;
- limits above 100 or below 1 are rejected;
- negative offsets and malformed semantic folder tokens are rejected.

## Data boundary

The model contains no mailbox address, tenant/account identifier, URL, selector, cookie, token, auth header, storage state or browser profile path. Fixture message keys and subjects are synthetic test material only.

## Compatibility and activation boundary

OUT-010 does not register an `outlook_*` MCP tool, does not add a worker operation and does not promote any Outlook capability into the effective Capability Registry. Live/browser implementation requires later UI-contract evidence and adapter work.

## Acceptance coverage

Tests prove deterministic inbox/archive results, attachment/read metadata, bounded pagination, fail-closed readiness/folder/input handling and continued zero Outlook public Tool/Capability Registry exposure.

## Dependency gate

This work is stacked on OUT-007, which is already GREEN on its stacked base. OUT-010 must not merge until OUT-002..OUT-007 have been integrated in order and post-merge `main` is GREEN after each predecessor. It will then be retargeted and revalidated with the complete mandatory gate suite.

## Integration reconciliation

The delta is integrated in `main` (clean branch rebased on GREEN `main` and merged through PR #307). Mandatory CI gates (compile/lint/type/contracts/tests, image build + Trivy + SBOM, filesystem/dependency/secret scanning) were GREEN on the merged PR and the post-merge `main` gate set was re-executed locally at `12b363c`.

This records mock-mode integration only. No live Microsoft tenant was contacted, no Outlook capability is promoted to SUPPORTED, the Outlook application stays RESERVED with no public `outlook_*` MCP tool, and the Planner public tool ABI is unchanged.
