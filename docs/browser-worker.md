# Planner MCP — Browser Worker

Status: specification (implementation-grade). This document specifies a service; it does **not**
claim the service exists. Every requirement is `PLANNED` unless a release note says otherwise
(`GOV-090`).
Canonical upstream: [docs/vision.md](./vision.md)
Related: [docs/architecture.md](./architecture.md) · [docs/security.md](./security.md) · [docs/privacy-boundary.md](./privacy-boundary.md) · [docs/governance.md](./governance.md) · [docs/ui-contract.md](./ui-contract.md) · [docs/authentication-and-mfa.md](./authentication-and-mfa.md) · [docs/tool-catalog.md](./tool-catalog.md)

Requirement IDs (`WORKER-xxx`) are stable, never reused, never renumbered.

---

## 1. Nature and boundary

**WORKER-001 — Private internal service.** `planner-browser-worker` is Zone W (`ARCH-003`). Its
only client is the control plane's `worker_client` (`ARCH-015`, `ARCH-090`). It has no public
identity, no user-facing surface and no MCP surface of its own.

**WORKER-002 — FastAPI-compatible HTTP/JSON interface** on `:8090`, never published to the host or
the internet, reachable only on the `internal: true` Docker network (`ARCH-032`, `ARCH-035`,
`ARCH-036`).

**WORKER-003 — Playwright/Chromium only, internally.** Browser primitives (navigate, click, type,
evaluate, screenshot, selector resolution) exist exclusively inside this service. They are never
exposed as MCP tools, never accepted as MCP arguments, never echoed to a caller (`ARCH-021`,
`SEC-005`, `TOOL-005`).

**WORKER-004 — The worker authorises nothing.** Policy lives in the control plane (`ARCH-073`).
The worker enforces *safety* invariants (contract, account context, read-back) but never decides
whether an operation is permitted.

**WORKER-005 — The worker holds the highest-value asset**: the authenticated professional session.
It is treated accordingly: minimal surface, no exports, no diagnostics that leak session material.

**WORKER-006 — Sanitized outputs only.** The worker returns structured domain data plus sanitized
status. Never cookies, tokens, storage state, headers, raw DOM, full URLs or screenshots of
authenticated content (`SEC-002`, `PRIV-064`, `UI-071`).

---

## 2. Runtime, profile and isolation

**WORKER-010 — Base image** is the official Playwright Python image, pinned by digest
(`ARCH-120`).

**WORKER-011 — Non-root.** Runs as a dedicated unprivileged user with `no-new-privileges:true` and
`cap_drop: [ALL]` (`ARCH-121`).

**WORKER-012 — Profile location and permissions.** The Chromium user-data directory lives in the
named volume `browser-profile`, mounted only into this service, owned by the worker user, mode
`0700` (`AUTH-011`, `PRIV-051`).

**WORKER-013 — Prohibited mounts.** No Docker socket, no host home directory, no personal browser
profile, no arbitrary host bind mounts — not even for debugging (`ARCH-122`, `PRIV-050`,
`PRIV-052`).

**WORKER-014 — Writable surface is minimal**: the profile volume plus a tmpfs scratch. Everything
else is read-only where the runtime permits.

**WORKER-015 — Process ownership.** The worker owns the entire Chromium process tree it spawns and
is responsible for reaping it. No externally launched browser is adopted, and no browser is left
running after shutdown.

**WORKER-016 — Single browser context per profile.** One persistent context, bound to one
professional account (`AUTH-010`, `PRIV-036`). The worker never opens a second profile or an
incognito context to work around a blocked state.

**WORKER-017 — Restart preserves the session.** A worker restart must not destroy the profile
volume; the session survives, but the auth state resets to `UNKNOWN` until re-probed
(`ARCH-124`, `AUTH-025`).

**WORKER-018 — No profile export, no state dump.** There is no endpoint, flag, or diagnostic that
copies the profile out of the volume (`PRIV-034`).

---

## 3. Concurrency and resource locking

**WORKER-040 — One operation at a time per profile.** A single Chromium profile cannot be driven
concurrently. The worker serialises operations behind a profile-level lock; a second request either
queues within a bounded wait or is refused with `WORKER_BUSY`.

**WORKER-041 — Typed locks.** Locks are typed by profile and, for mutations, additionally by target
external identifier, so an unrelated read cannot be starved by an unrelated mutation queue
(`ARCH-041`).

**WORKER-042 — Bounded queue.** Queue depth and wait time are configured; exceeding either is
`WORKER_BUSY`, never an unbounded backlog.

**WORKER-043 — Locks are released deterministically** on completion, error, timeout and shutdown.
A crashed operation must not leave a permanent lock; locks carry an expiry.

**WORKER-044 — Authentication is exclusive.** While an authentication attempt is live, Planner
operations on that profile are refused with `AUTH_REQUIRED`/`MFA_PENDING` rather than interleaved
(`AUTH-055`).

**WORKER-045 — Resource ceilings.** Maximum open pages, maximum operation duration and memory
guards are configured; breaching a ceiling terminates the operation and recycles the page, not the
profile.

---

## 4. Browser, page and session lifecycle

**WORKER-050 — Startup sequence.** Validate configuration → load and validate the UIContract
(`UI-082`) → ensure the profile directory exists with correct ownership → launch Chromium with the
persistent context → mark readiness. Failure at any step leaves the worker unready; it never starts
degraded.

**WORKER-051 — Page lifecycle.** Pages are created per operation, used, and closed. Long-lived
pages are not reused across unrelated operations to avoid state bleed.

**WORKER-052 — Navigation is contract-driven.** Target surfaces are declared in the UIContract; the
worker never navigates to a caller-supplied URL (`UI-004`).

**WORKER-053 — Session lifecycle is observation, not management.** The worker probes session
validity (`AUTH-034`) and reports state; it never refreshes tokens, replays cookies or performs a
silent re-login (`AUTH-056`).

**WORKER-054 — Shutdown.** Graceful shutdown drains the queue up to a bound, closes pages, closes
the context, and terminates the browser tree. Profile data is flushed, never deleted.

**WORKER-055 — Crash recovery.** A crashed Chromium is relaunched at most a configured number of
times within a window; beyond that the worker reports unready rather than looping.

---

## 5. Health, readiness and status

**WORKER-060 — Health** is liveness only: the process is up and the event loop responsive. It
performs no browser work and reveals no session information.

**WORKER-061 — Readiness** requires: Chromium launched, persistent context attached, UIContract
loaded and schema-valid, contract version reported, and lock subsystem operational. Readiness does
**not** require an authenticated session; authentication is reported separately.

**WORKER-062 — Status payload fields** are limited to: `ready`, `contract_version`, `auth_state`
(one of the eight `AUTH-020` values), `browser_up`, `queue_depth`, `last_probe_at`. No identity, no
URLs, no tenant data.

**WORKER-063 — Readiness mismatch is drift.** If the worker's `contract_version` differs from the
control plane's, the control plane fails closed with `UI_DRIFT` (`UI-083`, `ARCH-082`).

---

## 6. Authentication evidence extraction

**WORKER-070 — The worker is the only component that observes the login surface.** It detects
sign-in requirement, MFA challenge, number-matching digits and Conditional Access blockers via
UIContract-declared probes.

**WORKER-071 — Extraction is sanitizing by construction.** The extractor emits exactly the five
fields of `AUTH-040`; there is no code path that can attach page text, DOM, URLs or identity to an
auth event.

**WORKER-072 — No credential interaction.** The worker never types into a password field, never
submits credentials, never auto-selects an MFA number (`AUTH-002`, `AUTH-044`).

**WORKER-073 — Conditional Access detection is terminal.** On detection the worker aborts the
attempt, reports `BLOCKER_CONDITIONAL_ACCESS`, and performs no user-agent or platform mutation
(`AUTH-070`, `AUTH-071`, `PRIV-022`).

**WORKER-074 — Account context extraction** returns only the sanitized fields of `AUTH-032`.

---

## 7. Plan and task read operations, read-back probes

**WORKER-080 — Reads are contract-driven and structural.** A read resolves a UIContract entry,
navigates to the declared surface, extracts the declared fields, and returns a typed structure. No
scraping outside the contract.

**WORKER-081 — Preconditions are verified before extraction**: auth state `AUTHENTICATED`, account
context match, contract entry attested to at least `UI_ATTESTED` (`UI-061`).

**WORKER-082 — Returned data is tagged untrusted.** Everything derived from rendered UI carries
`trust_level = untrusted_ui_derived` and is treated as data, never as instructions
(prompt-injection posture, [docs/threat-model.md](./threat-model.md)).

**WORKER-083 — Partial extraction is reported as partial.** Missing declared fields yield an
explicit incomplete result, never silently defaulted values.

**WORKER-084 — Read-back probes are first-class.** The worker exposes read-back as an internal
primitive used after mutations, executing the entry's declared probe and returning a strict
comparison outcome (`UI-060`, `ARCH-101`).

**WORKER-085 — Mutation preconditions (future releases).** Before any mutation the worker
validates, in order: auth state, account/tenant context (`AUTH-030`), UIContract entry attestation
and version (`UI-062`), and the presence of a control-plane authorisation token for that specific
request. Any failure aborts before touching the UI. Today the control plane denies all mutations
(`SEC-007`).

**WORKER-086 — No mutation without a declared read-back.** An entry lacking a probe cannot be used
for a mutation, regardless of policy.

---

## 8. Errors, timeouts, retries, circuit breaking

**WORKER-090 — Typed sanitized errors only.** Errors are emitted from a closed taxonomy with a
sanitized description. Playwright stack traces, page text and Microsoft error strings are never
propagated (`ARCH-112`, `AUTH-080`).

| Class | Meaning |
| --- | --- |
| `WORKER_UNAVAILABLE` | Not ready, browser down, or unreachable |
| `WORKER_BUSY` | Lock/queue bound exceeded |
| `WORKER_TIMEOUT` | Operation exceeded its bound |
| `WORKER_INTERNAL` | Unexpected internal failure, sanitized |
| `AUTH_*` | Authentication classes (`AUTH-080`) |
| `UI_*` | Contract classes ([docs/ui-contract.md](./ui-contract.md) section 9) |

**WORKER-091 — Every operation is time-bounded** at three levels: navigation, locator resolution,
and total operation. Exceeding any bound yields `WORKER_TIMEOUT`.

**WORKER-092 — Retries only for idempotent reads**, bounded and jittered. Non-idempotent operations
are never retried unless a read-back has proven the prior attempt had no effect (`ARCH-093`,
`SEC-040`).

**WORKER-093 — Circuit breaker.** Repeated failures of a class (browser crashes, contract
unresolved, auth failures) open a breaker that fast-fails subsequent requests for a cool-down
window and reports the reason. The breaker fails closed and never half-opens into a mutation.

**WORKER-094 — Never degrade into assumption.** An unavailable or ambiguous condition never yields
a synthesised or cached-as-live result (`ARCH-092`).

---

## 9. Worker API boundary (expected shape, not an implementation claim)

**WORKER-100 — The internal surface is small, typed and versioned.** It carries an API version;
the control plane refuses a version it does not understand.

**WORKER-101 — Expected endpoints.**

| Endpoint | Method | Purpose |
| --- | --- | --- |
| `/health` | GET | Liveness only (`WORKER-060`) |
| `/readiness` | GET | Readiness + `contract_version` (`WORKER-061`) |
| `/status` | GET | Sanitized status payload (`WORKER-062`) |
| `/auth/status` | GET | Current `auth_state` + sanitized event fields |
| `/auth/start` | POST | Begin an interactive attempt; returns `operation_id` |
| `/auth/resume` | POST | Re-observe an attempt by `operation_id` |
| `/auth/account-context` | GET | Sanitized account/tenant context (`AUTH-032`) |
| `/contract/status` | GET | Loaded contract version and per-entry attestation states |
| `/read/plans` | POST | Contract-driven plan listing |
| `/read/plan` | POST | Single plan read by opaque external id |
| `/read/tasks` | POST | Contract-driven task listing |
| `/read/task` | POST | Single task read |
| `/read/project-snapshot` | POST | Composite read across attested entries |
| `/probe/read-back` | POST | Execute a declared read-back probe |
| `/smoke` | POST | Non-mutating internal self-check |

**WORKER-102 — No generic execution endpoint.** There is no exec, click, type, evaluate, navigate
or screenshot endpoint. Proposing one requires an ADR and is rejected by default (`ARCH-022`).

**WORKER-103 — Internal commands are capability-keyed**, not selector-keyed. The control plane
sends a capability key and typed arguments; the worker resolves locators locally from the contract.

**WORKER-104 — No published port, no host route, no direct client.** Enforced by compose
configuration and asserted in tests (`ARCH-035`).

**WORKER-105 — Authentication of the internal hop** relies on network isolation today; if the two
services are ever split across hosts, mutual authentication becomes mandatory first (`ARCH-038`,
`SEC-070`).

---

## 10. Tests

**WORKER-110** Compose assertion: worker service has no published ports and sits on an internal
network.
**WORKER-111** Container assertions: non-root user, `no-new-privileges`, `cap_drop: [ALL]`, no
docker socket, no home mount, profile mode `0700`.
**WORKER-112** Startup refuses an invalid or schema-failing UIContract.
**WORKER-113** Concurrency: second operation queues or returns `WORKER_BUSY`; locks expire; no
deadlock after a crash.
**WORKER-114** Error serializer: no stack traces, no page text, no URLs, no identity in any error.
**WORKER-115** Retry policy: reads retried, non-idempotent operations never retried.
**WORKER-116** Circuit breaker opens, fast-fails, and cannot half-open into a mutation.
**WORKER-117** Mutation attempt without account-context verification or contract attestation is
refused before any UI interaction.
**WORKER-118** No endpoint returns cookies, storage state, DOM or screenshots (response-shape
assertion across the whole API).

---

## 12. Operator-only GUI handoff (host-side, fail-closed)

**WORKER-120 — Operator-only GUI handoff is host-side and lives outside the worker.** It provides a
loopback-only VNC view of the running worker profile for an operator. It is never an MCP tool, never
exposed over HTTP, and never containerised alongside the worker.

**WORKER-121 — Start fails closed.** It refuses unless the production checkout is clean, the expected
`browser-worker` container exists and is `healthy`, every required host binary is present, every
loopback port is free, no other live Chromium holds the profile, and the profile ownership is exactly
the numeric `1001:1001`. Any single failure aborts start with no side effects.

**WORKER-122 — GUI stack order is fixed and reversible.** Launch order is Xvfb → x11vnc → websockify
→ Chromium; teardown order is the reverse. On any launch failure the started processes are rolled back
in reverse order and `browser-worker` is restarted to healthy.

**WORKER-123 — Network exposure is loopback-only.** Xvfb disables TCP; x11vnc and websockify bind
`127.0.0.1`; noVNC is served locally only. The handoff never exposes anything beyond `127.0.0.1` and
never touches Cloudflare.

**WORKER-124 — Chromium runs as the profile owner, with no CDP.** The host Chromium is launched as the
numeric uid/gid `1001:1001` via `setpriv` against the named Docker volume profile and carries no
`--remote-debugging-port`, `--remote-debugging-pipe`, or CDP surface. The profile is never chowned;
ownership is preserved.

**WORKER-125 — Stop touches only browser-worker.** `stop` terminates the GUI stack, then restarts
`browser-worker` and waits for healthy. The control plane is never stopped, started, or referenced.

**WORKER-126 — State is sanitized and external to the profile.** Only PIDs, health booleans, and the
loopback endpoint are stored in a state file outside the profile. No credentials, cookies, tokens,
URLs, or browser data are written. No passwords/tokens appear in logs.

**WORKER-127 — No credential or tenant handling.** The handoff performs zero authentication, never
reads or writes cookies/storage state, and never contacts M365. It is observation-only at the GUI layer.

See `docs/operator-gui-handoff.md` and `scripts/operator_gui_handoff.py`.

---

## 13. Traceability

| ID range | Area |
| --- | --- |
| WORKER-001…006 | Nature and boundary |
| WORKER-010…018 | Runtime, profile, isolation |
| WORKER-040…045 | Concurrency and locking |
| WORKER-050…055 | Browser/page/session lifecycle |
| WORKER-060…063 | Health and readiness |
| WORKER-070…074 | Auth evidence extraction |
| WORKER-080…086 | Reads and read-back |
| WORKER-090…094 | Errors, timeouts, retries, breaker |
| WORKER-100…105 | API boundary |
| WORKER-110…118 | Tests |
| WORKER-120…127 | Operator-only GUI handoff |


