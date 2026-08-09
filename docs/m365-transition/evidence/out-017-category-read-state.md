# OUT-017 — Category listing/read state

Status: **PREIMPLEMENTED_STACKED_AWAITING_OUT_016**

## Objective

Add bounded, synthetic-only Outlook category listing and per-message category read state on top of the OUT-002 fixture and OUT-007 readiness gate. Category mutation is explicitly out of scope.

## Semantic model

`m365_mcp.apps.outlook.category_reads` defines:

- `CategoryColorToken` — closed tenant-neutral colour vocabulary with no rendering or tenant palette semantics;
- `SyntheticCategory` — category key, display name and colour token;
- `CategoryAssignment` — explicit synthetic message-to-category link;
- `CategoryUsage` / `CategoryListResult` — catalog with derived assignment counts;
- `MessageCategoryState` — deterministic sorted category keys for one message;
- `list_fixture_categories()` / `read_fixture_message_categories()` — fail-closed read entry points.

## Fail-closed rules

- non-synthetic fixtures are rejected;
- OUT-007 read-only discovery readiness is mandatory;
- catalogs above 100 categories are rejected;
- duplicate category keys are rejected;
- duplicate message/category assignment pairs are rejected;
- assignments referencing unknown categories or unknown synthetic messages are rejected;
- more than 25 category assignments on one message is rejected;
- malformed/whitespace-bearing semantic tokens are rejected;
- colour tokens outside the closed enum are rejected;
- unknown message keys are rejected.

## Security/activation boundary

OUT-017 introduces no URL, path, selector, XPath, JavaScript, HTTP header, cookie, token, storage state, browser profile, mailbox address, account or tenant identity, and performs no mutation. A dedicated test asserts these substrings are absent from the projections.

It registers no public `outlook_*` MCP tool, adds no worker operation, promotes no Outlook capability and has no Microsoft Graph dependency.

## Acceptance coverage

Eight tests cover usage counts, deterministic sorted per-message state, empty state, projection sanitization, unready/non-synthetic rejection, invalid catalogs and assignments, bounded token/enum validation, unknown message keys and continued zero Outlook Tool/Capability Registry exposure.

## Execution attestation

Synthetic/mock execution only. No authenticated Outlook session, tenant, mailbox or live UI was contacted, and no live attestation is claimed.

## Inherited base defect

The OUT-013..OUT-015 stack is missing `m365_mcp.result_references`, which exists on `main`. See `out-016-folder-navigation-reads.md`. OUT-017 neither introduces nor masks that defect; local gates were executed with the upstream file present as an uncommitted compensation and it is not committed on this branch.

## Dependency gate

Stacked on OUT-016. Must not merge until OUT-002..OUT-016 are integrated in order and every predecessor is post-merge GREEN, and until the inherited `result_references` defect is resolved.
