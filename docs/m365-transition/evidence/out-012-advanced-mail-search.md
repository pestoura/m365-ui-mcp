# OUT-012 — Advanced mail search

Status: **PREIMPLEMENTED_STACKED_AWAITING_OUT_011**

## Objective

Add a bounded semantic search over reviewed Outlook message metadata without exposing a generic query language or browser primitive.

## Search vocabulary

`m365_mcp.apps.outlook.mail_search.MailSearchRequest` supports only:

- optional case-insensitive subject substring (`query`, maximum 200 characters);
- optional semantic folder key;
- optional read/unread filter;
- optional attachment-presence filter;
- bounded offset/limit pagination, maximum 100 rows.

`search_fixture_messages()` currently executes only over the synthetic OUT-002 fixture and requires OUT-007 read-only discovery readiness.

## Fail-closed rules

- non-synthetic fixtures are rejected;
- unready discovery is rejected;
- unknown fixture folders are rejected;
- empty/oversized queries are rejected;
- malformed folder tokens, negative offsets and out-of-range limits are rejected.

## Security boundary

OUT-012 is not a generic search DSL and accepts no URL, selector, XPath, JavaScript, HTTP header, cookie, token, storage-state value or browser profile path. The query is only a bounded subject substring applied to synthetic fixture data.

No public `outlook_*` tool, worker operation or effective Outlook capability is activated. Live search requires later UI-contract evidence and adapter/acceptance gates.

## Acceptance coverage

Tests prove case-insensitive subject matching, combined folder/read/attachment filters, bounded empty results, input/folder fail-closed behavior and continued zero Outlook Tool/Capability Registry exposure.

## Dependency gate

This work is stacked on OUT-011. It must not merge until the complete OUT-002..OUT-011 chain is integrated in order and each predecessor is post-merge GREEN. It will then be retargeted and fully revalidated.
