# Planner MCP — Security

Status: specification (implementation-grade)
Canonical upstream: [docs/vision.md](./vision.md)
Related: [docs/architecture.md](./architecture.md) · [docs/threat-model.md](./threat-model.md) · [docs/privacy-boundary.md](./privacy-boundary.md) · [docs/governance.md](./governance.md)

Requirement IDs (`SEC-xxx`) are stable. Where a requirement is specified but not yet implemented
it is marked **PLANNED**. A `PLANNED` requirement is never described as an existing control, in
this document or anywhere else (`GOV-090`).

---

## 1. Hard invariants

**SEC-001 — Fail closed.** Every ambiguous, unverified, unknown or degraded condition results in
refusal, not in a best-effort attempt. This includes: unknown tool, unmatched policy rule,
unattested UIContract, drifted UIContract, unavailable worker, unverified read-back, ambiguous
tenant/account, and any Conditional Access managed-device requirement.

**SEC-002 — No secret material anywhere in the system.** Passwords, cookies, bearer/refresh
tokens, storage state, session identifiers, authorization headers, private keys and device
certificates are never committed to the repository, never written to logs or metrics, never
persisted in the MCP state store, never placed in environment variables for transport, and never
returned through the MCP surface.

**SEC-003 — The persistent professional browser profile is the only authentication mechanism.**
There is no credential injection path. Authentication happens interactively, human-driven, into
the worker's profile.

**SEC-004 — No device enrolment, ever.** See [docs/privacy-boundary.md](./privacy-boundary.md)
`PRIV-010`. `BLOCKER_CONDITIONAL_ACCESS` is terminal; bypass and spoofing are forbidden.

**SEC-005 — No raw browser primitives on the public surface.** (`ARCH-020`, `ARCH-021`.)

**SEC-006 — No success without verification.** Read-back is mandatory before any operation is
reported successful (`ARCH-041`, `ARCH-101`).

**SEC-007 — Current release performs no mutations.** The policy engine denies every non-read
tool. This is enforced, not merely intended.

---

## 2. Policy model

**SEC-010** Decisions are exactly three: `ALLOW`, `DENY`, `REQUIRE_APPROVAL`.

**SEC-011** Default is `DENY`. An operation is permitted only by an explicit matching allow rule.
Unknown tools are denied by identity, not by pattern.

**SEC-012** The policy engine runs in the control plane, before any egress to the worker, and is
the sole authorisation authority (`ARCH-073`). Tools do not self-authorise. The worker performs
no authorisation. Hermes performs no authorisation.

**SEC-013** Policy inputs: tool identity, declared mutation class, capability evidence, UIContract
version and attestation state, runtime mode (`mock`/`live`), configuration flags, target scope
(tenant/plan), and approval state where relevant.

**SEC-014** Policy evaluation is deterministic and free of side effects other than audit emission.
The same inputs always yield the same decision.

**SEC-015** Policy changes are governed artefacts (`GOV-030`): they require review, a rationale, a
test, and a version bump of the policy contract.

### 2.1 Mutation classes

**SEC-020** Every tool declares exactly one mutation class:

| Class | Meaning | Default decision | Reversible | Approval |
| --- | --- | --- | --- | --- |
| `READ` | No state change of any kind | `ALLOW` (when preconditions hold) | n/a | No |
| `SAFE_WRITE` | Additive/low-impact change, trivially reversible, no data loss | `ALLOW` under policy, or `REQUIRE_APPROVAL` by configuration | Yes | Configurable |
| `GOVERNED_WRITE` | Meaningful business change (assignment, scheduling, dependency, field values) | `REQUIRE_APPROVAL` | Yes, with compensation | Yes |
| `DESTRUCTIVE` | Deletion, irreversible removal, bulk/structural change | `REQUIRE_APPROVAL` and additionally gated | Often no | Yes, always |

**SEC-021** A tool without a declared mutation class is denied. Absence is not `READ`.

**SEC-022** Escalation is one-way: a tool may never be reclassified to a lower class without an
ADR and a governance decision (`GOV-020`).

**SEC-023** `DESTRUCTIVE` operations additionally require: an attested UIContract, a defined
compensation or explicit "no compensation possible" acknowledgement in the approval prompt, and a
saga with checkpoints.

---

## 3. Approvals

**SEC-030 — Digest binding.** An approval is bound to a canonical digest of the exact request:
tool identity, target `external_id`, normalised arguments, mutation class, and schema/contract
versions. A digest mismatch invalidates the approval.

**SEC-031 — Persistence.** Approvals are persisted in the control-plane state store (`approval`
table), not held in memory and not held in the notification channel.

**SEC-032 — Single use, atomic consumption.** Consumption is an atomic state transition
(`PENDING → CONSUMED`) performed under the resource lock. A consumed approval can never be reused.
Concurrent consumption attempts: exactly one succeeds.

**SEC-033 — Expiry.** Approvals expire after a bounded, configured TTL. Expired approvals are
rejected, never renewed silently.

**SEC-034 — Informed approval.** The approval prompt must present intent, target identity, the
concrete change (before → after where knowable), mutation class, reversibility and the
compensation plan. An approval prompt that cannot show the target unambiguously must not be
issued. *(PLANNED)*

**SEC-035 — Attribution.** Approval records carry approver identity, channel, timestamp and the
notification reference. *(PLANNED)*

**SEC-036 — Non-replayable across sessions.** Approvals are not transferable between requests,
sagas, resources or time windows. There is no "approve all" and no standing approval.

**SEC-037** Hermes conveys approval requests and captures the human response, but the authoritative
approval record lives only in the control-plane state store (`THR-101`).

---

## 4. Idempotency, read-back, concurrency

**SEC-040 — Read-back before retry.** A non-idempotent operation is never retried blindly. If the
outcome is unknown, the system reads back the target state and decides from observed reality.

**SEC-041 — Idempotency keys.** Mutating operations carry an idempotency key derived from tool
identity, target `external_id`, argument digest and contract version. A recorded result for the
key is returned without re-execution.

**SEC-042 — Result hashing.** Idempotency records store a result hash so that a replayed key with
divergent context is detected rather than silently served.

**SEC-043 — Typed resource locks.** Concurrent operations on the same `external_id` are
serialised by a typed lock with an owner, a purpose and an expiry. Lock acquisition failure fails
closed.

**SEC-044 — Sagas and checkpoints.** Multi-step operations run as sagas; each step records a
checkpoint and declares its compensation. A saga interrupted mid-flight is resumable or
compensatable, never left in an unknown state without an audit record.

**SEC-045 — Compensation honesty.** Where no compensation exists, the operation is classified
`DESTRUCTIVE` and the approval prompt states that it is irreversible.

**SEC-046 — Retries and circuit breaking only where safe.** Bounded retries with backoff are
permitted for idempotent reads and for transport-level failures that provably did not reach the
target. A circuit breaker isolates a failing worker and fails closed (`WORKER_UNAVAILABLE`); it
never falls back to an unverified path.

**SEC-047 — Stable identity.** `external_id` (plus `source_id`) is the stable correlation key
between desired state, observed state, locks, idempotency and evidence.

---

## 5. Secrets handling

**SEC-050 — Deny-list redaction at the emission boundary.** A central redaction module removes
credential-shaped material (passwords, cookies, `Authorization` headers, bearer/JWT patterns,
refresh tokens, session identifiers, e-mail addresses, user/tenant identifiers) before
serialisation of any log, metric, tool result, evidence record or notification.

**SEC-051 — Redaction applies to exceptions.** Exception messages, context dictionaries and stack
traces pass through redaction. Third-party library logging is routed through the same handler
where technically possible; where it is not, that library's logging is disabled rather than left
unredacted.

**SEC-052 — Low-cardinality metrics.** Metric labels are restricted to an allow-list: `tool`,
`decision`, `mutation_class`, `outcome`, `error_code`, `mode`. Identifiers, URLs, e-mail
addresses and free text are never labels.

**SEC-053 — No secrets in configuration transport.** Operational secrets (e.g. Cloudflare API
tokens) live in the operator's secret store, are referenced by path, and are never printed,
echoed, committed, or copied into the MCP state or the repository.

**SEC-054 — File-backed secret pattern.** Where a secret is genuinely required by a component, it
is provided as a file with restrictive permissions (`0600`, owner-only) and read at startup, not
passed as a command-line argument and not embedded in an image layer. Pattern adopted from the
`hermes-mcp-bridge` secret handling model.

**SEC-055 — Rotation.** Any secret that exists must be rotatable without a code change. Rotation
procedures are governance artefacts (`GOV-060`).

**SEC-056 — No secret ever reaches the MCP surface.** No tool returns, echoes or accepts secret
material, including "for diagnostics".

---

## 6. Service-to-service authentication

**SEC-070 — HMAC-signed internal requests.** *(PLANNED)* Control-plane → worker requests carry an
HMAC signature over method, path, body digest, timestamp and a nonce, using a file-backed shared
secret (`SEC-054`), with a bounded clock skew window and nonce replay rejection. Modelled on the
`hermes-mcp-bridge` signed-request pattern. Today the equivalent protection is network isolation
only (`ARCH-032`, `THR-030`) — this is stated as a gap, not as a control.

**SEC-071 — Control-plane caller authentication.** *(PLANNED)* Defence in depth behind the
Cloudflare portal: the control plane independently verifies a caller credential rather than
trusting the edge alone (`THR-001`, `THR-090`).

**SEC-072** If the control plane and worker are ever deployed on different hosts, `SEC-070`
becomes a blocking prerequisite, together with TLS on the TB-2 hop (`ARCH-038`).

---

## 7. Authentication and MFA posture

**SEC-060 — MFA via Microsoft Authenticator only.** The system never renders, requests, relays,
proxies, stores or transports MFA codes, one-time passwords or push-approval material. The human
approves in the Authenticator app.

**SEC-061 — Sanitized auth telemetry only.** Auth state is exposed as sanitized metadata
(`tenant_display`, `account_kind`, `profile`, `device_enrolment`, state machine status) and never
as raw identity, raw session data or screenshots of the sign-in surface.

**SEC-062 — Interactive-only sign-in.** There is no headless credential submission path. The
password is never present in the system (`PRIV-070`).

**SEC-063 — Conditional Access.** A managed/compliant-device requirement produces
`BLOCKER_CONDITIONAL_ACCESS` and terminates the operation. No enrolment, no device certificate, no
user-agent or device spoofing, no alternative authentication route.

---

## 8. Provenance and evidence

**SEC-080 — Every claim carries provenance.** Evidence records include source, timestamp, runtime
mode, UIContract version, trust level, and the operation/saga they belong to.

**SEC-081 — Trust labelling.** UI-derived data is `trust_level = untrusted_ui_derived` throughout
its lifetime and is never promoted by transformation.

**SEC-082 — Redacted evidence.** Evidence is redacted before storage. Screenshots of authenticated
content are excluded (`ARCH-103`).

**SEC-083 — Append-only audit.** Authorisation decisions, approvals, consumptions, lock
acquisitions, saga transitions and refusals are recorded as append-only audit events, separate
from operational logs.

**SEC-090 — Audit integrity.** *(PLANNED)* Hash-chaining of audit events so that retroactive
modification is detectable (`THR-012`, `THR-112`).

---

## 9. Container and runtime hardening

**SEC-100** Both services run as **non-root** (the worker uses the official Playwright image's
unprivileged user).

**SEC-101** `security_opt: [no-new-privileges:true]` on every service.

**SEC-102** `cap_drop: [ALL]` on every service. No capability is added back without an ADR.

**SEC-103** Read-only root filesystem where practical: enforced on the control plane. The worker
requires a writable persistent profile directory — a documented, reviewed exception; its writable
surface is limited to the profile volume and tmpfs.

**SEC-104** `tmpfs` for scratch (`/tmp` with `noexec,nosuid`, and `/dev/shm` sized for Chromium).

**SEC-105** The worker is attached only to an `internal: true` Docker network and publishes **no
port**. The control plane publishes only to `127.0.0.1`.

**SEC-106** **No host Docker socket** is mounted into any container.

**SEC-107** **No host home directory, no personal profile directory and no personal data path** is
mounted into any container (`PRIV-050`).

**SEC-108** Named volumes are single-owner: `browser-profile` → worker only; `mcp-state` →
control plane only. They are never shared.

**SEC-109** Resource limits (memory, pids) are applied to bound the blast radius of a wedged or
hostile Chromium. Both services declare `mem_limit` and `pids_limit` in the compose deployment;
the worker is sized for Chromium and the control plane is sized for an async Python service. A
service without both limits fails the container hardening parity gate.

---

## 9a. Container hardening parity matrix

**REL-004** Container hardening parity with the Planner/Hermes baseline is a declared,
machine-checked control set rather than an assertion spread across unrelated tests.

Parity is asserted against the Planner/Hermes container baseline. Every row is machine-checked by
`tests/test_rel_004_container_hardening_parity.py` against `docker-compose.yml` and the two
Dockerfiles, so drift fails CI rather than being discovered in deployment.

| Control | Control plane | Browser worker | Reference |
| --- | --- | --- | --- |
| Non-root runtime user | `planner` (uid 10001) | `pwuser` (image-provided) | `SEC-100` |
| `no-new-privileges` | required | required | `SEC-101` |
| `cap_drop: [ALL]` | required | required | `SEC-102` |
| Read-only root filesystem | required | documented exception (writable profile) | `SEC-103` |
| tmpfs scratch with `noexec,nosuid` | required | required (plus sized `/dev/shm`) | `SEC-104` |
| No published port beyond loopback | `127.0.0.1` only | none | `SEC-105` |
| No Docker socket mount | required | required | `SEC-106` |
| No host/home/personal bind mount | required | required | `SEC-107`, `PRIV-050` |
| Single-owner named volume | `mcp-state` | `browser-profile` | `SEC-108` |
| Memory limit | required | required | `SEC-109` |
| PID limit | required | required | `SEC-109` |
| Base image pinned by digest | required | required | `SEC-110` |
| Installer toolchain removed from runtime image | required | required | `SEC-110`, `SEC-111` |

---

## 10. Supply chain

**SEC-110 — Base image digest pinning.** Both base images are pinned by digest. A blocking CI gate
fails the build if any `FROM` reference loses its digest. Digest updates are deliberate, reviewed
changes.

**SEC-111 — Vulnerability scanning.** Trivy filesystem and image scans run in CI and **fail** on
CRITICAL/HIGH findings.

**SEC-112 — SBOM.** A CycloneDX SBOM is produced for both images and uploaded as a CI artifact for
every release build.

**SEC-113 — Dependency and secret scanning.** Dependency scanning and secret scanning run in CI;
secret-scanning findings are blocking.

**SEC-114 — Pinned dependencies.** Application dependencies are version-pinned; upgrades are
reviewed changes, not automatic.

**SEC-115 — CI never touches a live tenant.** CI runs in mock mode only, with no live credentials
present in the pipeline (`ARCH-084`).

**SEC-116 — Closed browser egress policy.** The browser worker evaluates every request URL against
a fail-closed allowlist before it leaves the browser:

1. `about:`, `blob:` and `data:` are local browser resources and do not constitute network egress;
2. any non-`https` scheme is blocked (`NON_HTTPS_BLOCKED`);
3. a host is allowed only when it matches a reviewed Microsoft 365 suffix
   (`MICROSOFT_M365_ALLOWLIST`); everything else is blocked (`HOST_NOT_ALLOWLISTED`);
4. **API surfaces are denied even inside allowed Microsoft suffixes.** `graph.microsoft.com` and
   the other Graph endpoints are blocked with `API_SURFACE_DENIED`, because the product substrate
   is the reviewed UI and Graph is a non-dependency (ADR-008, `THR-134`);
5. the decision is enforced at the Playwright route handler, which aborts blocked requests; there
   is no proxy, fetch or generic navigation primitive to bypass it.

Adding a host suffix, or removing a denied API surface, is a reviewed policy change with recorded
evidence — never an incidental edit.

---

## 11. Error taxonomy (fail-closed codes)

| Code | Meaning | Terminal |
| --- | --- | --- |
| `POLICY_DENIED` | Policy engine refused the operation | Yes |
| `APPROVAL_REQUIRED` | Human approval needed; no side effect occurred | No (pending) |
| `UI_CONTRACT_UNATTESTED` | Live operation attempted against an unattested contract | Yes |
| `UI_DRIFT` | UIContract version mismatch between control plane and worker | Yes |
| `WORKER_UNAVAILABLE` | Browser worker unreachable or circuit open | Yes |
| `AUTH_REQUIRED` | No valid professional session in the persistent profile | Yes |
| `BLOCKER_CONDITIONAL_ACCESS` | Conditional Access requires a managed/compliant device | Yes — never bypass |

**SEC-120** Error codes are stable, machine-readable, and carry no content, identity or secret
material in their message or context.

---

## 12. Security requirement index

| ID range | Area |
| --- | --- |
| SEC-001…007 | Hard invariants |
| SEC-010…023 | Policy model and mutation classes |
| SEC-030…037 | Approvals |
| SEC-040…047 | Idempotency, read-back, concurrency |
| SEC-050…056 | Secrets handling |
| SEC-060…063 | Authentication and MFA |
| SEC-070…072 | Service-to-service authentication |
| SEC-080…090 | Provenance, evidence, audit |
| SEC-100…109 | Container and runtime hardening |
| SEC-110…116 | Supply chain and egress |
| SEC-120 | Error taxonomy |
