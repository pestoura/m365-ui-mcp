# OUT-019 — Pin/Snooze read state

Status: **PREIMPLEMENTED_STACKED_AWAITING_OUT_018**

## Objective

Add bounded, synthetic-only Outlook pin and snooze read state on top of the OUT-002 fixture and OUT-007 readiness gate. Pin and snooze mutation are out of scope.

## Semantic model

`m365_mcp.apps.outlook.pin_snooze_reads` defines:

- `SnoozeState` — closed `NOT_SNOOZED` / `SNOOZED` state;
- `PinSnoozeMarker` — per-message pin flag plus optional snooze target;
- `PinSnoozeReadState` — projection with derived `is_snooze_elapsed` and `is_hidden_from_default_list`;
- `PinSnoozeListResult` — fixture-wide listing with pinned, snoozed and hidden counters;
- `read_fixture_pin_snooze_state()` / `list_fixture_pin_snooze_state()` — fail-closed read entry points.

Pin and snooze are modelled together because both are list-presentation states: pinning promotes a message in a listing and snoozing defers it. `is_hidden_from_default_list` is derived, never stored, and is true only while a snooze has not yet elapsed relative to the caller-supplied reference offset.

### Relative time model

Snooze targets use bounded integer day offsets (±3650) evaluated against `reference_day_offset`, consistent with OUT-018. No absolute timestamp, timezone or wall-clock read is introduced, so results are deterministic.

## Fail-closed rules

- non-synthetic fixtures are rejected;
- OUT-007 read-only discovery readiness is mandatory;
- a snoozed message requires `snooze_until_day_offset`;
- a snooze offset on a non-snoozed message is rejected;
- simultaneous pinned and snoozed state is rejected as semantically contradictory;
- offsets outside ±3650 days are rejected;
- non-boolean `is_pinned` and non-integer offsets are rejected;
- states outside the closed enum are rejected;
- duplicate markers per message key are rejected;
- markers referencing unknown synthetic messages are rejected;
- malformed and unknown message keys are rejected;
- out-of-range `reference_day_offset` is rejected.

Messages absent from the marker catalog read as neither pinned nor snoozed.

## Security/activation boundary

OUT-019 introduces no URL, selector, XPath, JavaScript, HTTP header, cookie, token, storage state, browser profile, mailbox address, account or tenant identity, and no absolute timestamp. A dedicated test asserts these substrings are absent from the projection.

It registers no public `outlook_*` MCP tool, adds no worker operation, promotes no Outlook capability and has no Microsoft Graph dependency.

## Acceptance coverage

Nine tests cover counters, snooze-elapsed transitions across reference offsets, the absent-marker default, projection sanitization, unready/non-synthetic rejection, contradictory markers, duplicate/dangling catalogs, unknown message keys, out-of-range offsets and continued zero Outlook Tool/Capability Registry exposure.

## Execution attestation

Synthetic/mock execution only. No authenticated Outlook session, tenant, mailbox or live UI was contacted, and no live attestation is claimed.

## Inherited base defect

The OUT-013..OUT-015 stack is missing `m365_mcp.result_references`. See `out-016-folder-navigation-reads.md`. OUT-019 neither introduces nor masks it, and does not commit the compensation file.

## Dependency gate

Stacked on OUT-018. Must not merge until OUT-002..OUT-018 are integrated in order and every predecessor is post-merge GREEN, and until the inherited `result_references` defect is resolved.
