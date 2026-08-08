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

