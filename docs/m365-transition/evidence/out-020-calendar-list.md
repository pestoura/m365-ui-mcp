# OUT-020 — Calendar list

Status: **INTEGRATED_CLEAN_ON_MAIN**

## Objective

Add a bounded, synthetic-only Outlook calendar listing on top of the OUT-002 fixture and the OUT-007 readiness gate. It is the first Calendar READ foundation and deliberately excludes events, occurrences, availability and any mutation, which arrive in OUT-021..OUT-024 and later phases.

## Semantic model

`m365_mcp.apps.outlook.calendar_list` defines:

- `CalendarKind` — closed `PRIMARY` / `SECONDARY` / `GROUP` / `BIRTHDAY` classification;
- `CalendarColorToken` — closed semantic colour vocabulary, never a raw UI colour value;
- `SyntheticCalendar` — tenant-neutral calendar definition with readability and default-view flags;
- `CalendarNode` — sanitized read-only projection;
- `CalendarListResult` — bounded listing with calendar/readable counters and the resolved default calendar key;
- `list_fixture_calendars()` / `read_fixture_calendar()` — fail-closed read entry points.

Calendar identity is expressed only as an opaque semantic key. No mailbox address, account, tenant, calendar URL, share link or absolute timestamp is modelled.

## Fail-closed rules

- non-synthetic fixtures are rejected;
- OUT-007 read-only discovery readiness is mandatory;
- an empty catalog is rejected;
- catalogs above the bounded size are rejected;
- duplicate `calendar_key` entries are rejected;
- a catalog without exactly one `PRIMARY` calendar is rejected;
- a catalog without exactly one default-view calendar is rejected;
- a default-view calendar that is not readable is rejected;
- non-boolean flags and values outside the closed enums are rejected;
- malformed and unknown `calendar_key` reads are rejected.

## Security/activation boundary

OUT-020 introduces no URL, selector, XPath, JavaScript, HTTP header, cookie, token, storage state, browser profile, mailbox address, account or tenant identity, and no absolute timestamp. A dedicated test asserts these substrings are absent from the projection.

It registers no public `outlook_*` MCP tool, adds no worker operation, promotes no Outlook capability and has no Microsoft Graph dependency. `calendar.read` remains an `UNOBSERVED` OUT-004 discovery candidate and no live calendar support is claimed.

## Acceptance coverage

Eight tests cover listing counters and ordering, single-calendar read projection, projection sanitization, unready/non-synthetic rejection, invalid calendar definitions, invalid catalogs (empty, duplicate, missing/duplicated primary and default), unknown/malformed keys, and continued zero Outlook Tool/Capability Registry exposure.

## Execution attestation

Synthetic/mock execution only. No authenticated Outlook session, tenant, mailbox, calendar or live UI was contacted, and no live attestation is claimed.

## Dependency gate

Integrated cleanly from post-merge GREEN `main` after OUT-019. Successors OUT-021..OUT-024 build event, availability, scheduling-assistant and shared-calendar reads on this catalog.
