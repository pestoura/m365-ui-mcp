# OUT-014 — Attachment metadata/list

Status: **INTEGRATED_CLEAN_ON_MAIN**

## Objective

Add bounded Outlook attachment metadata/list reads while explicitly excluding attachment content retrieval. Controlled retrieval remains OUT-015.

## Metadata model

`m365_mcp.apps.outlook.attachment_metadata.SyntheticAttachment` contains only:

- opaque synthetic attachment key;
- synthetic parent message key;
- file name;
- MIME type;
- non-negative byte size.

The default synthetic catalog contains one attachment for `msg-002`. No bytes, body content, storage locator, URL or download handle is present.

`list_fixture_attachment_metadata()` requires a synthetic fixture, OUT-007 read-only discovery readiness, an existing synthetic message and an internally consistent attachment catalog.

## Fail-closed rules

- malformed semantic attachment/message keys are rejected;
- invalid MIME types and negative sizes are rejected;
- duplicate attachment keys are rejected;
- attachment entries referencing unknown messages are rejected;
- attachment metadata must agree with the parent message `has_attachments` state;
- explicit empty catalogs remain empty and are not silently replaced by defaults;
- unready/non-synthetic execution is rejected.

## Security/activation boundary

OUT-014 exposes metadata only. It introduces no attachment bytes, download URL, storage locator, mailbox/account/tenant identity, selector, XPath, JavaScript, token, cookie, auth header or browser profile path.

It registers no public `outlook_*` MCP tool, adds no worker operation and promotes no Outlook capability. Controlled attachment retrieval is intentionally deferred to OUT-015.

## Acceptance coverage

Tests prove metadata-only behavior, empty metadata for messages without attachments, fail-closed dangling/mismatched catalogs, bounded metadata validation and continued zero Outlook Tool/Capability Registry exposure.

## Dependency gate

This work is stacked on OUT-013. It must not merge until OUT-002..OUT-013 are integrated in order and every predecessor is post-merge GREEN. It will then be retargeted to `main` and fully revalidated.

## Integration reconciliation

The delta is integrated in `main` (clean branch rebased on GREEN `main` and merged through PR #314). Mandatory CI gates (compile/lint/type/contracts/tests, image build + Trivy + SBOM, filesystem/dependency/secret scanning) were GREEN on the merged PR and the post-merge `main` gate set was re-executed locally at `12b363c`.

This records mock-mode integration only. No live Microsoft tenant was contacted, no Outlook capability is promoted to SUPPORTED, the Outlook application stays RESERVED with no public `outlook_*` MCP tool, and the Planner public tool ABI is unchanged.
