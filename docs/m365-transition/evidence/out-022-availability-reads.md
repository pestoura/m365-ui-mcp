# OUT-022 — Availability/free-busy reads

Status: **INTEGRATED_CLEAN_ON_MAIN**

## Objective

Derive bounded, synthetic-only Outlook free-busy availability from the OUT-021 event model over the OUT-020 calendar catalog. Meeting-time suggestion, booking, working-hours tenant settings and any mutation remain out of scope.

## Semantic model

`m365_mcp.apps.outlook.availability_reads` defines:

- `AvailabilityState` — closed `FREE` / `TENTATIVE` / `BUSY` / `OUT_OF_OFFICE` state;
- `AvailabilityWindow` — closed bounded relative query window (day range, daily minute range, slot size);
- `AvailabilitySlot` — one relative slot with derived state and overlapping-event count;
- `AvailabilityResult` — deterministic slot sequence with free/busy counters;
- `read_fixture_availability()` — the single fail-closed read entry point.

### Derivation rules

Each event contributes a relative interval. A slot overlaps an event when the intervals intersect. `FREE`-presented events never block a slot; among blocking events the strongest state wins, ordered `TENTATIVE` < `BUSY` < `OUT_OF_OFFICE`. Cancelled events are excluded because OUT-021 excludes them by default, so a cancelled meeting cannot hold a slot.

### Relative time model

The window uses `from_day_offset` / `to_day_offset` (±3650, at most 31 days), `day_start_minute` / `day_end_minute` inside a single day, and a `slot_minutes` size of at least 5 that must divide the daily span exactly. No absolute timestamp, timezone, wall-clock read or calendar-server free-busy call is introduced, so slot boundaries and ordering are fully deterministic.

## Fail-closed rules

- a non-`AvailabilityWindow` argument is rejected, so no free-form window string can be interpreted;
- the OUT-021 event gate is re-executed, which itself re-executes the OUT-020 calendar gate and the OUT-007 readiness and synthetic-fixture gates;
- non-synthetic fixtures and unready discovery are rejected;
- inverted day ranges, windows above the bounded day count and out-of-range day offsets are rejected;
- daily minute bounds outside a single day, or a start not preceding the end, are rejected;
- slot sizes below the minimum, above the daily span, or not dividing the span exactly are rejected;
- non-integer window fields are rejected;
- an unknown calendar scope is rejected.

## Security/activation boundary

OUT-022 introduces no URL, selector, XPath, JavaScript, HTTP header, cookie, token, storage state, browser profile, mailbox address, attendee address, account or tenant identity, and no absolute timestamp. Slots expose only relative positions, a closed state and a count — never event subjects — so free-busy reads cannot leak calendar content. A dedicated test asserts the forbidden substrings are absent from the projection.

It registers no public `outlook_*` MCP tool, adds no worker operation, promotes no Outlook capability and has no Microsoft Graph dependency. `calendar.read` remains an `UNOBSERVED` OUT-004 discovery candidate and no live free-busy support is claimed.

## Acceptance coverage

Ten tests cover busy-slot derivation around a timed event, all-day out-of-office blocking, calendar-scoped and multi-day windows with tentative precedence, cancelled events not blocking, projection sanitization, unready/non-synthetic rejection, invalid window definitions, rejection of non-window input, inherited calendar/event gate enforcement, and continued zero Outlook Tool/Capability Registry exposure.

## Execution attestation

Synthetic/mock execution only. No authenticated Outlook session, tenant, mailbox, calendar, attendee or live UI was contacted, and no live attestation is claimed.

## Dependency gate

Integrated cleanly from post-merge GREEN `main` after OUT-021. Successors OUT-023 and OUT-024 build scheduling-assistant structural reads and shared-calendar reads on this availability model.
