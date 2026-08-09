# OUT-023 — Scheduling Assistant structural reads

Status: **INTEGRATED_CLEAN_ON_MAIN**

## Objective

Model the Outlook Scheduling Assistant *structurally* by composing the OUT-022 availability grid for a bounded set of synthetic participants. It reports where relative free-busy grids overlap. Meeting booking, invitation, response handling, attendee lookup and directory resolution remain firmly out of scope.

## Semantic model

`m365_mcp.apps.outlook.scheduling_assistant` defines:

- `ParticipantRole` — closed `ORGANIZER` / `REQUIRED` / `OPTIONAL` structural role;
- `SlotFeasibility` — closed `ALL_FREE` / `REQUIRED_FREE` / `CONFLICTED` classification;
- `SyntheticParticipant` — opaque participant key bound to an optional synthetic calendar scope;
- `ParticipantGridRow` — one participant's relative availability row;
- `SchedulingSlot` — one composed grid column with feasibility and participant counters;
- `SchedulingGrid` — the deterministic composed projection;
- `read_fixture_scheduling_grid()` — the single fail-closed read entry point.

### Composition rules

Every participant's row is produced by OUT-022 for that participant's calendar scope, so all rows share identical column boundaries. A column is `ALL_FREE` when no participant is blocked, `REQUIRED_FREE` when only `OPTIONAL` participants are blocked, and `CONFLICTED` when an `ORGANIZER` or `REQUIRED` participant is blocked. `required_free_slot_count` counts the columns a meeting could structurally occupy.

## Fail-closed rules

- a non-`AvailabilityWindow` argument is rejected;
- OUT-022 is re-executed per participant, so the OUT-021 event gate, the OUT-020 calendar gate and the OUT-007 readiness and synthetic-fixture gates all apply;
- an empty participant catalog is rejected;
- catalogs above the bounded participant count are rejected;
- duplicate `participant_key` entries are rejected;
- a catalog without exactly one `ORGANIZER` is rejected;
- a `participant_key` containing `@` is rejected so no address identity can be smuggled through the key;
- malformed participant and calendar tokens are rejected;
- an unknown participant calendar scope is rejected.

## Security/activation boundary

OUT-023 introduces no URL, selector, XPath, JavaScript, HTTP header, cookie, token, storage state, browser profile, mailbox address, attendee address, directory record, account or tenant identity, and no absolute timestamp. Grid rows and columns expose only opaque participant keys, closed states and counters — never event subjects — so scheduling composition cannot leak calendar content. Dedicated assertions cover both the forbidden substrings and the absence of event subject text.

It registers no public `outlook_*` MCP tool, adds no worker operation, promotes no Outlook capability and has no Microsoft Graph dependency. `calendar.read` remains an `UNOBSERVED` OUT-004 discovery candidate and no live Scheduling Assistant support is claimed.

## Acceptance coverage

Ten tests cover per-participant row composition, organizer conflict classification, optional-participant tolerance producing `REQUIRED_FREE`, projection sanitization including subject absence, unready/non-synthetic rejection, invalid participant definitions including address-like keys, invalid catalogs (empty, duplicate, missing/duplicated organizer), rejection of non-window input, inherited calendar/availability gate enforcement, and continued zero Outlook Tool/Capability Registry exposure.

## Execution attestation

Synthetic/mock execution only. No authenticated Outlook session, tenant, mailbox, calendar, attendee, directory or live UI was contacted, and no live attestation is claimed.

## Dependency gate

Integrated cleanly from post-merge GREEN `main` after OUT-022. Successor OUT-024 adds shared-calendar reads.
