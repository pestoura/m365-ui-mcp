# OUT-024 — Shared-calendar reads

Status: **INTEGRATED_CLEAN_ON_MAIN**

## Objective

Enforce delegated shared-calendar permission levels over the OUT-020..OUT-022 read surface, so a shared calendar can never project more than its granted level allows. Sharing invitations, permission grants, revocation and any mutation remain out of scope.

## Semantic model

`m365_mcp.apps.outlook.shared_calendar_reads` defines:

- `SharedCalendarPermission` — closed, ordered `NONE` < `FREE_BUSY_ONLY` < `LIMITED_DETAILS` < `FULL_DETAILS`;
- `SharedCalendarScope` — opaque delegated scope key bound to one synthetic calendar;
- `SharedCalendarReadState` — what the scope may structurally read, before reading anything;
- `read_shared_calendar_state()` / `read_shared_calendar_availability()` / `list_shared_calendar_events()` — fail-closed read entry points.

### Permission enforcement

`FREE_BUSY_ONLY` permits OUT-022 availability only. `LIMITED_DETAILS` additionally permits OUT-021 event reads but replaces every subject with `REDACTED_BY_SHARED_CALENDAR_PERMISSION`. Only `FULL_DETAILS` projects real synthetic subjects. `NONE` blocks every read. Enforcement happens before delegation to the underlying reader, so a lower level cannot obtain a higher-level projection.

## Fail-closed rules

- non-synthetic fixtures and unready discovery are rejected;
- the underlying OUT-022/OUT-021/OUT-020 gates are re-executed, so no predecessor boundary can be bypassed;
- an empty scope catalog is rejected;
- catalogs above the bounded scope count are rejected;
- duplicate `scope_key` entries are rejected;
- a `scope_key` containing `@` is rejected so no delegate address identity can be smuggled through the key;
- malformed scope and calendar tokens are rejected;
- unknown `scope_key` reads are rejected;
- a scope pointing at an unknown calendar is rejected;
- availability reads below `FREE_BUSY_ONLY` and event reads below `LIMITED_DETAILS` are rejected explicitly rather than silently degraded.

## Security/activation boundary

OUT-024 introduces no URL, selector, XPath, JavaScript, HTTP header, cookie, token, storage state, browser profile, mailbox address, delegate address, directory record, share link, sharing invitation, account or tenant identity, and no absolute timestamp. A dedicated test asserts the forbidden substrings are absent from the read-state projection, and a further test asserts a `LIMITED_DETAILS` listing does not leak the underlying synthetic subject text.

It registers no public `outlook_*` MCP tool, adds no worker operation, promotes no Outlook capability and has no Microsoft Graph dependency. `calendar.read` remains an `UNOBSERVED` OUT-004 discovery candidate and no live shared-calendar support is claimed.

## Acceptance coverage

Eleven tests cover permission-to-read-state mapping across all four levels, free-busy scope reading availability while being denied events, subject redaction at `LIMITED_DETAILS`, subject preservation at `FULL_DETAILS`, `NONE` blocking every read, projection sanitization, unready/non-synthetic rejection, invalid scope definitions including address-like keys, invalid catalogs and unknown keys, inherited calendar/event gate enforcement, and continued zero Outlook Tool/Capability Registry exposure.

## Execution attestation

Synthetic/mock execution only. No authenticated Outlook session, tenant, mailbox, calendar, delegate, sharing relationship or live UI was contacted, and no live attestation is claimed.

## Dependency gate

Integrated cleanly from post-merge GREEN `main` after OUT-023. This completes the OUT-020..OUT-024 Calendar READ foundations. Any live calendar claim still requires separate evidence-backed attestation.
