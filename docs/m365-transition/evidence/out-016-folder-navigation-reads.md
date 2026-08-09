# OUT-016 — Folder listing/navigation reads

Status: **INTEGRATED_CLEAN_ON_MAIN**

## Objective

Add bounded, synthetic-only Outlook folder listing and semantic folder navigation reads on top of the OUT-002 fixture and OUT-007 readiness gate.

## Semantic model

`m365_mcp.apps.outlook.folder_reads` defines:

- `SyntheticFolder` — tenant-neutral folder definition with semantic folder key, display name and optional parent key;
- `FolderNode` — read-only projection with derived depth, child count, message count and unread count;
- `FolderListResult` — full bounded hierarchy for one synthetic fixture;
- `FolderNavigationResult` — one folder plus its ancestor and direct-child keys;
- `list_fixture_folders()` / `navigate_fixture_folder()` — fail-closed read entry points.

"Navigation" here means resolving a semantic position inside a validated synthetic tree. It issues no UI action, no page transition and no browser command.

## Fail-closed rules

- non-synthetic fixtures are rejected;
- OUT-007 read-only discovery readiness is mandatory;
- empty catalogs and catalogs above 200 folders are rejected;
- duplicate folder keys are rejected;
- the catalog key set must exactly match the fixture folder set;
- unknown `parent_key` references are rejected;
- self-parenting, cycles and hierarchies deeper than 8 levels are rejected;
- malformed/whitespace-bearing semantic tokens are rejected;
- unknown navigation targets are rejected.

## Security/activation boundary

OUT-016 introduces no URL, path, CSS/XPath selector, JavaScript, click/goto primitive, HTTP header, cookie, token, storage state, browser profile, mailbox address, account or tenant identity. A dedicated test asserts these substrings are absent from the navigation projection.

It registers no public `outlook_*` MCP tool, adds no worker operation, promotes no Outlook capability and has no Microsoft Graph dependency. Registry emptiness for the `outlook` application is asserted by test.

## Acceptance coverage

Nine tests cover hierarchy counts, nested ancestor/child resolution, projection sanitization, unready/non-synthetic rejection, invalid catalogs, cyclic hierarchies, bounded token validation, unknown navigation targets and continued zero Outlook Tool/Capability Registry exposure.

## Execution attestation

Synthetic/mock execution only. No authenticated Outlook session, tenant, mailbox or live UI was contacted, and no live attestation is claimed.

## Known base defect (inherited, not introduced by OUT-016)

The OUT-015 branch imports `m365_mcp.result_references`, which exists on `main` but not in the OUT-013..OUT-015 stack. On the unmodified stack the entire Outlook test suite therefore fails at collection with `ModuleNotFoundError`, and PR #284 CI fails at the Ruff step.

OUT-016 does not fix and does not mask this. Local gate execution for OUT-016 was performed with the upstream `main` copy of `result_references.py` present in the working tree as an uncommitted compensation, so the OUT-016 result is measured rather than blocked. That file is deliberately **not** committed on this branch: it belongs to the OUT-015/integration reconciliation, which must resolve it by rebasing the stack onto current `main`.

## Dependency gate

Stacked on OUT-015. Must not merge until OUT-002..OUT-015 are integrated in order and every predecessor is post-merge GREEN, and until the inherited `result_references` defect is resolved. It will then be retargeted to `main` and fully revalidated.

## Integration reconciliation

The delta is integrated in `main` (clean branch rebased on GREEN `main` and merged through PR #316). Mandatory CI gates (compile/lint/type/contracts/tests, image build + Trivy + SBOM, filesystem/dependency/secret scanning) were GREEN on the merged PR and the post-merge `main` gate set was re-executed locally at `12b363c`.

This records mock-mode integration only. No live Microsoft tenant was contacted, no Outlook capability is promoted to SUPPORTED, the Outlook application stays RESERVED with no public `outlook_*` MCP tool, and the Planner public tool ABI is unchanged.
