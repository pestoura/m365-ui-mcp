# M365 Core Execution Status

This file is the execution overlay for the `CORE-*` definitions in `../roadmap-and-backlog.md`. It records only completed/executing gates; the roadmap remains the canonical definition of scope and order.

## Phase 1 — Product identity and shared-core extraction

| Key | Status | Evidence / decision |
|---|---|---|
| CORE-001 | PASS | Product identity ADR accepted in PR #215; merged to `main` at `24da6de7a88e18e7cc6f11b0216d91d602136816`; post-merge docs `31241171203` and CI `31241171204` SUCCESS. |
| CORE-002 | PASS | Repository renamed to `pestoura/m365-ui-mcp`; PR #216 merged to `main` at `7af511c1612573d9fc3822e37fa375901c3ec162`; post-merge docs `31241960632` and CI `31241960631` SUCCESS. |
| CORE-003 | PASS | Canonical namespaces/entry points; PR #217 merged to `09df4d3f1db9a370256dfd696b73c1a8e732881c`; post-merge docs `31242437571` and CI `31242437576` SUCCESS. |
| CORE-004 | PASS | Canonical `M365_*` with bounded historical aliases; PR #218 merged to `71d55d7c83f75e15808480081e214659c77dd8a1`; post-merge docs `31242924851` and CI `31242924852` SUCCESS. |
| CORE-005 | PASS | Generic control plane; PR #219 merged to `d7cd92c48258250248c53e2fd63828835f28c52a`; post-merge docs `31243362589` and CI `31243590216` SUCCESS. |
| CORE-006 | PASS | Generic browser/profile boundary; PR #220 merged to `ccf91b1afa61c7181b48fa43b4acfcb87ff78f9f`; post-merge docs `31254342686` and CI `31254342688` SUCCESS. |
| CORE-007 | PASS | Closed Application Registry; PR #221 merged to `d8d46fe9782abc104e6fd5580e7a0c0d269f8cd8`; post-merge docs `31254742904` and CI `31254742912` SUCCESS. |
| CORE-008 | PASS | Canonical Tool Registry; PR #222 merged to `1a8f182db8727dcc83550a795a01d48a49e120a2`; post-merge docs `31255232889` and CI `31255232909` SUCCESS. |
| CORE-009 | PASS | Metadata-driven semantic registration; PR #223 merged to `2c250af7763a325df34f53c826adea5c01e61a3d`; post-merge docs `31255688052` and CI `31255688039` SUCCESS. |
| CORE-010 | PASS | Bounded exposure profiles; PR #224 merged to `ccfb2c0382c1e812abad6517a5d735ddebe5ec62`; post-merge docs `31256189742` and CI `31256189728` SUCCESS. |

Phase 1 gate: **PASS / GREEN**.

## Phase 2 — Capability and UI contract redesign

| Key | Status | Evidence / decision |
|---|---|---|
| CORE-011 | PASS | Scoped Capability Registry merged through PR #225 to `3a53d44a77254810c701a04535b1ef2065302ab6`; post-merge docs `31257452439` and CI `31257452441` SUCCESS. |
| CORE-012 | PASS | Effective capability projection merged through PR #226 to `608bc854863c9e9fa756c20503c7c7d27d83d61a`; post-merge docs `31258381298` and CI `31258381284` SUCCESS. |
| CORE-013 | PASS | Fragmented UIContract storage merged through PR #227 to `9b1a8aeb3a9ab536d8b26eeaf45717e95fd34d86`; post-merge docs `31258954098` and CI `31258954095` SUCCESS. |
| CORE-014 | PASS | Per-fragment attestation merged through PR #228 to `66d03890492f072364c270b9a9c6b42958da086e`; post-merge docs `31259491871` and CI `31259491856` SUCCESS. |
| CORE-015 | PASS | Contract-set digest merged through PR #229 to `f41915de3dbdcb052993f1e31f2aca1637840add`; post-merge docs `31260020398` and CI `31260020388` SUCCESS. |
| CORE-016 | PASS | Closed locator strategy merged through PR #230 to `7c321271ce5eae042754f8b18480758b6cf0ead1`; post-merge docs `31261175335` and CI `31261175402` SUCCESS. |
| CORE-017 | PASS | Closed UI drift lifecycle merged through PR #231 to `b9322f676eddb06a22fe98ead9292f05f6fdc5ef`; post-merge docs `31264131559` and CI `31264131570` SUCCESS. |
| CORE-018 | PASS | Sanitized capability evidence persistence merged through PR #232 to `99f32929ab13c5068ac00410e8418abc9b8a7ef2`; post-merge docs `31264839172` and CI `31264839203` SUCCESS. |
| CORE-019 | PASS | Deterministic attestation workflow merged through PR #233 to `f7b89a4eb740fa561189bc1e62c4869d5242a644`; post-merge docs `31265582918` and CI `31265582939` SUCCESS. |
| CORE-020 | PASS | Versioned evidence lifetime/revalidation merged through PR #234 to `b60f9b80c22cba841265962d0308518b57667fd6`; post-merge docs `31266326587` and CI `31266326601` SUCCESS. |

Phase 2 gate: **PASS / GREEN** — CORE-011..020 are merged and all applicable post-merge gates completed successfully.

## Phase 3 — Browser, session and network hardening

| Key | Status | Evidence / decision |
|---|---|---|
| CORE-021 | PASS | FastAPI browser lifespan ownership merged through PR #235 to `f57514abf21188dd76a2065521506d9d2e18f5c7`; post-merge docs `31266922919` and CI `31266922911` SUCCESS. |
| CORE-022 | PASS | True liveness/readiness merged through PR #236 to `b3aef8e08f13621070e777bdca81921a95320aed`; post-merge docs `31267827191` and CI `31267827213` SUCCESS. Readiness is a fail-closed seven-signal AND gate over browser/profile/auth/UI contract/broker/protocol/lock. |
| CORE-023 | PASS | Session/Capability Broker merged through PR #237 to `6736a229c0a601ba40cc7308d6bcd193c71caf78`; post-merge docs `31268368222` and CI `31268368228` SUCCESS. Semantic grants are browser-session bound and export only bounded scope metadata. |
| CORE-024 | PASS | Account-context enforcement merged through PR #238 to `14a81643ba727ecd542a8cb31c2f7089161883a6`; post-merge docs `31268882024` and CI `31268882046` SUCCESS. Broker viability requires an explicitly verified professional expected-profile context. |
| CORE-025 | PASS | Controlled worker egress merged through PR #239 to `ec4780bf4614647afa39f88c5aa37d5a9e4e2b9c`; post-merge docs `31269569744` and CI `31269569738` SUCCESS, including both image Trivy HIGH/CRITICAL scans and both CycloneDX SBOMs. |
| CORE-026 | PASS | Profile-level serialized executor merged through PR #240 to `80925d16588727585e2e5fc991612a9b3fd9e1cf`; post-merge docs `31270440808` and CI `31270440807` SUCCESS. One active operation per profile, bounded waiting, typed `WORKER_BUSY`, and executor-backed `lock_viable` are proven. |
| CORE-027 | PASS | Page lifecycle isolation merged through PR #241 to `6466cc53bd583a18405766ff26a2bfcae11a43b4`; post-merge docs `31270948475` and CI `31270948476` SUCCESS. Fresh operation pages close on success, failure and cancellation without exporting persistent-session state. |
| CORE-028 | PASS | Typed worker operation protocol merged through PR #242 to `8b128075005095fede123896cbfda2ea3a331a7a`; post-merge docs `31271609551` and CI `31271609518` SUCCESS. Closed semantic envelopes reject generic browser-shaped inputs and preserve compatibility routes. |
| CORE-029 | PASS | Worker protocol negotiation merged through PR #243 to `b9afee847737f40db87a6bbc9dc5630784c3b0c7`; post-merge docs `31272558227` and CI `31272558224` SUCCESS. Compatibility is negotiated, revocable and fail closed by default. |
| CORE-030 | IMPLEMENTED_AWAITING_GATES | Closed sanitized worker error envelopes preserve safe codes, derive app/capability scope from the operation, strip raw exception context/input, and reject typed execution before protocol negotiation. |

## CORE-017..020 evidence/lifecycle boundary

UI lifecycle, evidence persistence, attestation and freshness remain separate reviewed concerns. Evidence is bound to the exact UIContractSet digest, contains no tenant/session content, and expiration/degradation is capability scoped. Current Planner fragments remain `UNVERIFIED_LIVE` until real controlled evidence is collected; no CI workflow authenticates to the real tenant.

## CORE-021..030 browser/session/network boundary

FastAPI lifespan owns Playwright/Chromium. Readiness remains a fail-closed seven-signal AND gate. The Session/Capability Broker binds only registered semantic capabilities to a process-owned authenticated session and returns bounded application/surface/account/container metadata; it exposes no generic browser primitive.

Account correctness is separately fail-closed: authentication alone is insufficient unless the sanitized professional expected-profile context is VERIFIED. Controlled egress preserves the private control-plane/worker network, adds a worker-only outbound path, and applies a closed Playwright request policy so an outbound route does not become arbitrary Internet access.

The profile executor supplies the lock/serialization subsystem: one active operation per professional profile, bounded queueing and explicit `WORKER_BUSY` when admission capacity is exhausted. Each admitted semantic operation can use a fresh page whose page-local state is destroyed at operation completion while the authenticated persistent context remains process-owned.

The typed worker protocol constrains dispatch to a closed semantic enum and exact argument families. Compatibility is separately established by explicit handshake state; shared source code or matching defaults do not satisfy readiness or typed-operation admission.

Worker failures are projected through a closed sanitized taxonomy. Raw exception messages, arbitrary exception context and malformed request values are not returned to the control plane; application/capability labels are derived from the closed operation vocabulary.

## CORE-024 boundary decision

`CORE-024` separates authentication from account correctness. An authenticated session is insufficient unless its sanitized account-context assertion is `VERIFIED`, professional and associated with the expected isolated profile. UNVERIFIED, AMBIGUOUS, WRONG_ACCOUNT and WRONG_TENANT all fail semantic authorization with `POLICY_DENIED`.

The account-context model intentionally does not persist or require raw tenant IDs, email addresses or user identifiers. The live `/account/context` route exposes only state/professional/expected_profile/valid flags.

## CORE-025 boundary decision

`CORE-025` makes worker outbound connectivity explicit without creating a public worker route. `browser-internal` remains Docker-internal; only the browser worker joins `m365-egress`; and Playwright aborts non-HTTPS or unreviewed outbound hosts by default.

CI validates the mechanism and network topology only. It does not authenticate to a real Microsoft tenant and therefore does not claim that the reviewed Microsoft domain set is complete for every live tenant flow. Any additional dependency discovered during controlled live evidence collection remains a reviewed policy change.

## CORE-026 boundary decision

`CORE-026` owns only profile-level serialization and bounded admission. The executor is internal application state, not a public API. It does not introduce page lifecycle behavior, a generic operation surface, protocol envelopes or protocol negotiation.

A configured executor makes `lock_viable=true`, but that signal alone cannot promote global readiness because all other readiness signals remain independently required.

## CORE-027 boundary decision

`CORE-027` isolates page-local state without isolating away the authenticated professional session. The persistent browser context remains the intended authentication boundary; every semantic operation gets a fresh internal page and that page is closed deterministically afterward.

Page acquisition itself exposes no navigation/selector/script capability through MCP or HTTP.

## CORE-028 boundary decision

`CORE-028` introduces a single private semantic dispatch surface backed by a closed operation enum, discriminated typed arguments and `extra=forbid` validation. It deliberately contains no URL, selector, XPath, JavaScript, headers, cookies, token or storage-state command field.

## CORE-029 boundary decision

`CORE-029` makes compatibility an explicit runtime handshake. The worker advertises bounded supported-version metadata, accepts only bounded numeric dotted peer versions, chooses a mutual version, and resets to incompatible when no intersection exists.

`protocol_compatible` is false on process start and follows negotiated state by default. CORE-030 additionally enforces the same compatibility requirement at typed-operation admission, so readiness and execution cannot disagree.

## CORE-030 boundary decision

`CORE-030` exposes only allowlisted semantic error codes, curated messages, retryability and operation-derived application/capability scope. Raw exception strings and arbitrary context never cross the typed worker boundary; unknown failures collapse to `WORKER_ERROR`.

FastAPI request-validation errors are also sanitized so rejected values are not echoed. Existing historical compatibility routes remain available; the stricter negotiated/error envelope applies to the typed operation protocol.

## Current compatibility invariants

- all 17 public `planner_*` tools remain `PRESERVE` under default profile;
- all 11 Planner capability keys are preserved;
- all 10 existing UI selectors are preserved exactly once and in historical order;
- mock mode cannot be interpreted as live support;
- Outlook remains `RESERVED`, with zero public tools/capabilities/selectors;
- no raw browser primitive/session-secret export is introduced;
- controlled worker egress does not expose an inbound worker route or generic Internet primitive;
- profile serialization does not expose profile paths or a generic executor endpoint;
- operation-scoped page isolation does not export pages, URLs, selectors, DOM or storage state;
- typed worker dispatch accepts only the closed semantic operation vocabulary and exact typed arguments;
- protocol compatibility is negotiated, revocable and fail closed for readiness and typed execution;
- typed worker failures do not echo raw internal exception/request content.

## Next gate

```text
CORE-030 PR CI/security/images/SBOM GREEN
        -> merge
        -> post-merge main GREEN
        -> Phase 3 PASS/GREEN
        -> CORE-031
```
