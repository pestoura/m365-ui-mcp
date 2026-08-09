# OUT-021 — Event list/get/search

Status: **INTEGRATED_CLEAN_ON_MAIN**

## Objective

Add bounded, synthetic-only Outlook calendar event reads on top of the OUT-020 calendar catalog and the OUT-007 readiness gate. Event creation, update, cancellation, invitation and response handling remain out of scope.

## Semantic model

`m365_mcp.apps.outlook.calendar_events` defines:

- `EventShowAs` — closed `FREE` / `TENTATIVE` / `BUSY` / `OUT_OF_OFFICE` availability presentation;
- `EventSensitivity` — closed `NORMAL` / `PRIVATE` classification;
- `SyntheticEvent` — tenant-neutral event bound to one synthetic calendar;
- `EventProjection` — sanitized projection with derived relative end position;
- `EventSearchRequest` / `EventSearchResult` — closed bounded query and deterministic result page;
- `list_fixture_events()` / `get_fixture_event()` / `search_fixture_events()` — fail-closed read entry points.

### Relative time model

Event position is expressed only as `start_day_offset` (±3650), `start_minute_of_day` (0..1439) and `duration_minutes` (1..43200), consistent with OUT-018/OUT-019. `end_day_offset` and `end_minute_of_day` are derived, never stored. No absolute timestamp, timezone, wall-clock read or ICS payload is introduced, so ordering and pagination are deterministic.

Results are ordered by start day, start minute and then `event_key`. Cancelled events are excluded unless `include_cancelled` is explicitly set.

## Fail-closed rules

- non-synthetic fixtures are rejected;
- OUT-007 read-only discovery readiness is mandatory;
- the OUT-020 calendar catalog gate is re-executed, so an invalid calendar catalog cannot be bypassed through event reads;
- duplicate `event_key` entries are rejected;
- events referencing an unknown `calendar_key` are rejected;
- catalogs above the bounded size are rejected;
- offsets, minutes-of-day and durations outside their bounded windows are rejected;
- an all-day event that does not start at minute zero or does not span whole days is rejected;
- non-boolean flags and values outside the closed enums are rejected;
- empty/oversized queries, inverted day windows, negative offsets and out-of-range page limits are rejected;
- unknown calendar scope and unknown/malformed `event_key` reads are rejected.

## Security/activation boundary

OUT-021 introduces no URL, selector, XPath, JavaScript, HTTP header, cookie, token, storage state, browser profile, mailbox address, attendee address, account or tenant identity, and no absolute timestamp. A dedicated test asserts these substrings are absent from the projection.

It registers no public `outlook_*` MCP tool, adds no worker operation, promotes no Outlook capability and has no Microsoft Graph dependency. `calendar.read` remains an `UNOBSERVED` OUT-004 discovery candidate and no live calendar support is claimed.

## Acceptance coverage

Ten tests cover default listing and ordering, opt-in cancelled events, derived relative end position for timed and all-day events, calendar/query/show-as/date-window filters with pagination, projection sanitization, unready/non-synthetic rejection, invalid event definitions, invalid search requests, duplicate/dangling catalogs and unknown keys, inherited OUT-020 calendar-gate enforcement, and continued zero Outlook Tool/Capability Registry exposure.

## Execution attestation

Synthetic/mock execution only. No authenticated Outlook session, tenant, mailbox, calendar or live UI was contacted, and no live attestation is claimed.

## Dependency gate

Integrated cleanly from post-merge GREEN `main` after OUT-020. Successors OUT-022..OUT-024 build availability, scheduling-assistant and shared-calendar reads on this event model.
