# OUT-011 — Message get/read

Status: **PREIMPLEMENTED_STACKED_AWAITING_OUT_010**

## Objective

Add a bounded semantic read for one Outlook message while keeping the implementation synthetic-only and Outlook globally `RESERVED`.

## Model

`m365_mcp.apps.outlook.message_get` defines an opaque `MessageGetRequest` keyed only by synthetic `message_key` and a bounded `MessageGetResult` containing the metadata available in the tenant-neutral fixture.

`get_fixture_message()` requires:

- `fixture.synthetic == true`;
- OUT-007 `ready_for_readonly_discovery == true`;
- an exact message-key match.

Unknown message keys and invalid/unready contexts fail closed.

## Current data boundary

The OUT-002 fixture currently provides subject, folder, read state and attachment-presence metadata. OUT-011 does not invent message body, sender/recipient or tenant identifiers that are absent from the fixture.

No mailbox address, account/tenant identifier, URL, selector, cookie, token, auth header, storage state or browser profile path is introduced.

## Activation boundary

OUT-011 does not register a public `outlook_*` MCP tool, add a worker operation or promote an Outlook capability. Live message reading remains gated by UI-contract evidence and later adapter/acceptance work.

## Acceptance coverage

Tests prove exact fixture message retrieval, read/attachment metadata preservation, fail-closed unknown/unready requests, semantic-key validation and continued zero Outlook Tool/Capability Registry activation.

## Dependency gate

This work is stacked on OUT-010. It must not merge until the complete OUT-002..OUT-010 predecessor chain is integrated in order and each post-merge `main` gate is GREEN. It will then be retargeted and fully revalidated.
