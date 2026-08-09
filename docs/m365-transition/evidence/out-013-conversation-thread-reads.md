# OUT-013 — Conversation/thread reads

Status: **PREIMPLEMENTED_STACKED_AWAITING_OUT_012**

## Objective

Add bounded semantic conversation/thread reads without inferring threads from subject text and without introducing a generic browser/search primitive.

## Explicit synthetic thread model

`m365_mcp.apps.outlook.conversation_reads` defines `SyntheticConversation`, an explicit tenant-neutral mapping from an opaque synthetic `conversation_key` to an ordered tuple of synthetic message keys.

The default fixture catalog deliberately declares thread membership explicitly. The implementation does not group by subject, sender, timestamps or other heuristics that could diverge from Microsoft thread identity.

`read_fixture_conversation()` requires:

- a synthetic fixture;
- OUT-007 read-only discovery readiness;
- a unique conversation catalog;
- an exact conversation-key match;
- every declared message key to exist in the synthetic fixture.

The returned `ConversationReadResult` preserves the explicitly declared message order and exposes only the same bounded message-list metadata already supported by OUT-010.

## Fail-closed rules

- empty/malformed conversation keys are rejected;
- empty or duplicate message membership is rejected;
- duplicate conversation keys are rejected;
- unknown conversations are rejected;
- dangling message references are rejected;
- unready or non-synthetic execution is rejected.

## Security/activation boundary

OUT-013 introduces no mailbox/account/tenant identity, URL, selector, XPath, JavaScript, query DSL, cookie, token, authorization header, storage state or browser profile path.

It registers no public `outlook_*` MCP tool, adds no worker operation and promotes no Outlook capability. Live thread identity/reading remains gated by reviewed UI-contract evidence and later adapter/acceptance work.

## Acceptance coverage

Tests prove explicit thread ordering, deterministic default catalog membership, fail-closed unknown/dangling/duplicate thread structures and continued zero Outlook Tool/Capability Registry exposure.

## Dependency gate

This work is stacked on OUT-012. It must not merge until the complete OUT-002..OUT-012 chain is integrated in order and every predecessor is post-merge GREEN. It will then be retargeted to `main` and fully revalidated with the mandatory gate suite.
