# OUT-018 — Flag/follow-up read state

Status: **PREIMPLEMENTED_STACKED_AWAITING_OUT_017**

## Objective

Add bounded, synthetic-only Outlook flag/follow-up read state on top of the OUT-002 fixture and OUT-007 readiness gate. Flag mutation and reminder scheduling are out of scope.

## Semantic model

`m365_mcp.apps.outlook.follow_up_reads` defines:

- `FollowUpState` — closed `NOT_FLAGGED` / `FLAGGED` / `COMPLETED` lifecycle;
- `FollowUpFlag` — per-message flag with optional start, due and completed markers;
- `FollowUpReadState` — read-only projection with derived `is_flagged` / `is_completed`;
- `FollowUpListResult` — fixture-wide listing with flagged, completed and overdue counters;
- `read_fixture_follow_up_state()` / `list_fixture_follow_up_state()` — fail-closed read entry points.

### Relative time model

Scheduling is expressed as integer **day offsets** relative to a caller-supplied `reference_day_offset`, never as absolute timestamps. This keeps the model tenant-neutral, timezone-free, clock-independent and deterministic under test. Offsets are bounded to ±3650 days. Mapping offsets to real dates is deliberately deferred to a later reviewed live adapter.

## Fail-closed rules

- non-synthetic fixtures are rejected;
- OUT-007 read-only discovery readiness is mandatory;
- an unflagged message must carry no scheduling markers;
- a completed follow-up requires `completed_day_offset`;
- `completed_day_offset` on a non-completed follow-up is rejected;
- `due_day_offset` earlier than `start_day_offset` is rejected;
- offsets outside ±3650 days are rejected;
- booleans are rejected where an integer offset is required;
- states outside the closed enum are rejected;
- duplicate flags for one message key are rejected;
- flags referencing unknown synthetic messages are rejected;
- malformed message keys and unknown message keys are rejected.

Messages absent from the flag catalog read as `NOT_FLAGGED` rather than raising, which is the correct read-only default.

## Security/activation boundary

OUT-018 introduces no URL, selector, XPath, JavaScript, HTTP header, cookie, token, storage state, browser profile, mailbox address, account or tenant identity, and no absolute timestamp. A dedicated test asserts these substrings are absent from the projection.

It registers no public `outlook_*` MCP tool, adds no worker operation, promotes no Outlook capability and has no Microsoft Graph dependency.

## Acceptance coverage

Eight tests cover counters and overdue derivation, per-message state including the unflagged default, projection sanitization, unready/non-synthetic rejection, inconsistent flag combinations, duplicate/dangling catalogs, unknown message keys, out-of-range reference offsets and continued zero Outlook Tool/Capability Registry exposure.

## Execution attestation

Synthetic/mock execution only. No authenticated Outlook session, tenant, mailbox or live UI was contacted, and no live attestation is claimed.

## Inherited base defect

The OUT-013..OUT-015 stack is missing `m365_mcp.result_references`. See `out-016-folder-navigation-reads.md`. OUT-018 neither introduces nor masks it, and does not commit the compensation file.

## Dependency gate

Stacked on OUT-017. Must not merge until OUT-002..OUT-017 are integrated in order and every predecessor is post-merge GREEN, and until the inherited `result_references` defect is resolved.
