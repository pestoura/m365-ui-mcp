# OUT-015 — Controlled attachment retrieval boundary

Status: **INTEGRATED_CLEAN_ON_MAIN**

## Objective

Define a controlled attachment-retrieval boundary that permits validated attachment bytes to move only into an injected artifact sink while the semantic MCP result contains an opaque CORE-045 reference rather than bytes or a raw storage locator.

## Boundary

`m365_mcp.apps.outlook.attachment_retrieval` defines:

- `SyntheticAttachmentPayload` — synthetic test payload bound to an attachment key, non-empty and capped at 10 MiB;
- `AttachmentArtifactSink` — narrow protocol accepting only attachment key, MIME type and validated bytes and returning an internal locator;
- `AttachmentRetrievalResult` — message/attachment metadata plus an `ArtifactReference`;
- `retrieve_synthetic_attachment()` — validates readiness, attachment-key equality and exact metadata/payload size before invoking the sink.

After storage, the payload is represented by a CORE-045 `ARTIFACT` reference. The raw locator is immediately reduced to its digest by `make_artifact_reference()` and is not projected. The result exposes content digest, MIME type, size and opaque reference id only.

## Fail-closed rules

- read-only discovery readiness is mandatory;
- attachment payload key must exactly match metadata;
- byte length must exactly match declared attachment size;
- empty and >10 MiB payloads are rejected;
- an empty artifact-sink locator is rejected;
- the sink is not invoked before metadata/payload validation passes.

## Security boundary

OUT-015 is not a generic downloader. It accepts no URL, path, selector, XPath, JavaScript, HTTP headers, cookies, token, storage state or browser profile information. Attachment bytes are never embedded in the semantic result and raw artifact locators are never projected.

The current implementation is synthetic-only and registers no public `outlook_*` tool or worker operation. Live retrieval requires a later reviewed adapter and authenticated read-only acceptance.

## Dependency gate

This work is stacked on OUT-014. It must not merge until OUT-002..OUT-014 are integrated in order and every predecessor is post-merge GREEN. It will then be retargeted to `main` and fully revalidated.

## Integration reconciliation

The delta is integrated in `main` (clean branch rebased on GREEN `main` and merged through PR #315). Mandatory CI gates (compile/lint/type/contracts/tests, image build + Trivy + SBOM, filesystem/dependency/secret scanning) were GREEN on the merged PR and the post-merge `main` gate set was re-executed locally at `12b363c`.

This records mock-mode integration only. No live Microsoft tenant was contacted, no Outlook capability is promoted to SUPPORTED, the Outlook application stays RESERVED with no public `outlook_*` MCP tool, and the Planner public tool ABI is unchanged.
