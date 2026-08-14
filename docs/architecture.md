# Planner MCP — Architecture

Status: specification (implementation-grade)
Canonical upstream: [docs/vision.md](./vision.md)
Related: [docs/threat-model.md](./threat-model.md) · [docs/security.md](./security.md) · [docs/governance.md](./governance.md) · [docs/privacy-boundary.md](./privacy-boundary.md)

Requirement IDs in this document are stable and traceable (`ARCH-xxx`). They may be referenced
from code, tests, ADRs, backlog items and release gates. IDs are never reused or renumbered;
withdrawn requirements are marked `WITHDRAWN` in place.

---

## 1. Purpose and scope

**ARCH-001** Planner MCP exposes Microsoft Planner Premium to MCP clients through a *semantic*
tool contract, executed by a private Playwright/Chromium browser worker operating a persistent
professional browser profile.

**ARCH-002** Microsoft Graph is **not** a functional gate and **not** the execution substrate.
The browser worker is authoritative. Any future Graph usage is an optimisation and must never
become a hard dependency of a semantic tool.

**ARCH-003** The system is composed of two separately deployable services with distinct trust
levels: the **control plane** and the **browser worker**. They are never merged into one process
or one container.

**ARCH-004** Hermes is **outside** the execution path. Hermes is used only for operational
notifications and human-in-the-loop (HITL) interactions. Hermes never drives the browser, never
holds Planner session material, and is never a required dependency for a read operation.

---

## 2. End-to-end topology

```
 ┌────────────────────────────────────────────────────────────────────────────┐
 │ Zone P — Public / untrusted caller                                         │
 │                                                                            │
 │   ChatGPT (or any MCP client)                                              │
 │        │  MCP over Streamable HTTP (authenticated at the portal edge)      │
 │        ▼                                                                   │
 │   Cloudflare MCP Server Portal        ── edge authn/authz, TLS, WAF, logs   │
 └───────────────┬────────────────────────────────────────────────────────────┘
                 │  TB-1  (public → control plane; only semantic MCP tools)
 ┌───────────────▼────────────────────────────────────────────────────────────┐
 │ Zone C — Control plane (semi-trusted, no browser, no credentials)          │
 │                                                                            │
 │   planner-mcp  (FastMCP, Streamable HTTP, :8080 loopback-bound)            │
 │     ├── tool layer          semantic tools only                            │
 │     ├── policy engine       ALLOW / DENY / REQUIRE_APPROVAL (fail-closed)   │
 │     ├── UIContract registry versioned selector contract + attestation       │
 │     ├── state store         SQLite (WAL) — no content, no secrets           │
 │     ├── approvals/sagas     persistent, non-replayable approvals            │
 │     ├── worker client       the ONLY egress to the worker                   │
 │     └── metrics/logging     low-cardinality, redacted, structured           │
 └───────────────┬────────────────────────────────────────────────────────────┘
                 │  TB-2  (private, internal-only Docker network, no host route)
 ┌───────────────▼────────────────────────────────────────────────────────────┐
 │ Zone W — Browser worker (high-value, holds the session)                    │
 │                                                                            │
 │   planner-browser-worker (FastAPI, :8090, host-published loopback 127.0.0.1:8090 only) │
 │     ├── UI action executor   click/type/navigate — INTERNAL ONLY            │
 │     ├── read-back verifier   post-condition confirmation                    │
 │     ├── auth/MFA detector    sanitized metadata only                        │
 │     └── Playwright driver                                                   │
 │            └── Chromium, persistent PROFESSIONAL profile (volume)           │
 └───────────────┬────────────────────────────────────────────────────────────┘
                 │  TB-3  (worker → Microsoft; untrusted rendered content back)
 ┌───────────────▼────────────────────────────────────────────────────────────┐
 │ Zone M — Microsoft (external, uncontrolled)                                 │
 │   Entra ID sign-in · Conditional Access · Microsoft Planner Premium web UI  │
 └────────────────────────────────────────────────────────────────────────────┘

 ┌────────────────────────────────────────────────────────────────────────────┐
 │ Zone H — Hermes (side channel, NOT in the execution path)                  │
 │   Operational notifications · HITL approval prompts · run summaries         │
 │   Receives sanitized events only. Cannot invoke browser actions.            │
 └────────────────────────────────────────────────────────────────────────────┘
```

**ARCH-005** The four zones (P, C, W, M) plus the side channel (H) are distinct trust zones and
distinct deployment boundaries. A component may never assume the trust level of another zone.

---

## 3. Component responsibilities

| ID | Component | Owns | Must never |
| --- | --- | --- | --- |
| **ARCH-010** | Cloudflare MCP Server Portal | TLS termination, caller authentication/authorisation, rate limiting, edge audit log | Terminate policy decisions; be the only authorisation layer |
| **ARCH-011** | Control plane (`planner_mcp`) | Semantic tool contract, policy, state, approvals, UIContract registry, evidence, metrics | Launch a browser, hold cookies/passwords, expose raw UI primitives |
| **ARCH-012** | Browser worker (`planner_browser_worker`) | Playwright session, UI actions, read-back verification, auth/MFA detection | Publish a port to the host or internet, accept calls from anything but the control plane, return raw session material |
| **ARCH-013** | Chromium persistent profile | Authenticated professional session state | Be shared with a personal profile, be copied out of its volume, be committed or backed up to the repo |
| **ARCH-014** | Hermes | Notifications, HITL prompts, human approval capture UX | Execute Planner operations, receive unredacted payloads, act as a policy authority on its own |

**ARCH-015** The control plane is the **only** client of the browser worker. There is exactly one
egress path (`planner_mcp.worker_client`). No other module opens a socket to Zone W.

---

## 4. Public surface vs internal surface

**ARCH-020** The **public MCP surface is semantic**. Tools express intent at the domain level
(`planner_plan_list`, `planner_task_get`, and later `create_plan`, `assign_task`,
`move_task_to_bucket`, `sync_state`). Tool names, arguments and results are stable domain
concepts, not UI mechanics.

**ARCH-021** Raw browser primitives — `click`, `type`, `navigate`, `evaluate`, `screenshot`,
selector strings, DOM fragments — are **internal only**. They exist solely on the TB-2 hop and
inside Zone W. They are never exposed as MCP tools, never returned to an MCP caller, and never
accepted as MCP tool arguments (directly or as pass-through fields).

**ARCH-022** Any proposal to expose a generic/escape-hatch tool (e.g. `browser_exec`,
`raw_action`, `run_script`) is rejected by default. An exception requires an ADR, a policy class
of at least `GOVERNED_WRITE`, an attested UIContract, and explicit approval per
[docs/governance.md](./governance.md).

**ARCH-023** Selectors are never accepted from the caller. Selectors originate exclusively from
the versioned UIContract registry.

---

## 5. Protocols, ports, network expectations

| ID | Hop | Protocol | Address/port | Exposure |
| --- | --- | --- | --- | --- |
| **ARCH-030** | Client → Portal | HTTPS / MCP Streamable HTTP | Cloudflare-managed hostname | Public |
| **ARCH-031** | Portal → Control plane | HTTP(S) MCP Streamable HTTP | control plane `:8080`, bound `127.0.0.1` in compose, reached via the Cloudflare connector | Not directly public |
| **ARCH-032** | Control plane → Worker | HTTP/JSON (FastAPI) | `http://browser-worker:8090` | Internal Docker network only (`internal: true`); host publishes worker loopback `127.0.0.1:8090` only |
| **ARCH-033** | Worker → Microsoft | HTTPS (Chromium) | Microsoft endpoints | Egress only |
| **ARCH-034** | Control plane → Hermes | HTTP webhook / message | Hermes endpoint | Egress only, sanitized payloads |

**ARCH-035** The browser worker MUST NOT be published on `0.0.0.0` or any public interface. It is
host-published exclusively at `127.0.0.1:8090`; verified by the loopback-only `ports:` mapping on
the worker service and by test enforcement.

**ARCH-036** The worker network is declared `internal: true`; the worker has no route to the
public internet other than what Chromium requires for Zone M. Egress restriction beyond this is a
tracked hardening item, not a claimed control.

**ARCH-037** The control plane binds to loopback on the host and is reached through the
Cloudflare connector. It is never bound to `0.0.0.0` on a host with a public interface without a
documented, reviewed exception.

**ARCH-038** Transport-level protection between Zone C and Zone W relies on network isolation.
If the two services are ever split across hosts, mutual authentication (HMAC-signed requests or
mTLS, see [docs/security.md](./security.md) `SEC-070`) becomes mandatory before that change ships.

---

## 6. Data and control flows

### 6.1 Read flow (semantic read, no mutation)

```
1. Client calls a semantic read tool via the portal.
2. Portal authenticates the caller and forwards the MCP request.
3. Control plane resolves the tool → capability → mutation class READ.
4. Policy engine evaluates → ALLOW (reads are permitted when preconditions hold).
5. UIContract registry check: version match + attestation state.
      mismatch → UI_DRIFT (fail closed)
      unattested + attestation required → UI_CONTRACT_UNATTESTED (fail closed)
6. Worker client issues an internal read request over TB-2.
7. Worker executes the read via Playwright against the persistent profile.
      auth missing → AUTH_REQUIRED
      CA blocks a managed-device requirement → BLOCKER_CONDITIONAL_ACCESS (stop, never bypass)
8. Worker returns structured, sanitized data (no cookies, no tokens, no raw DOM by default).
9. Control plane tags the payload trust_level = untrusted_ui_derived, redacts, records evidence.
10. Result returned to the client; metrics and structured logs emitted (low cardinality).
```

### 6.2 Mutation flow (future releases; specified now, disabled today)

```
1..5  as above, with mutation class SAFE_WRITE | GOVERNED_WRITE | DESTRUCTIVE.
6.  Policy engine → ALLOW | DENY | REQUIRE_APPROVAL.
7.  REQUIRE_APPROVAL → persist an approval record (single-use, bound to a request digest),
    notify via Hermes (HITL), and return APPROVAL_REQUIRED. No side effect occurs.
8.  On approval consumption: verify the approval is unconsumed, unexpired and digest-matched.
    Consumption is atomic; a consumed approval can never be replayed.
9.  Acquire a typed resource lock on the target external_id.
10. Idempotency check: if the idempotency key has a recorded result, return it (no re-execution).
11. Execute as a saga with checkpoints; each step is individually compensatable.
12. Read-back verification: the worker re-reads the mutated object and confirms post-conditions.
       unverified → the operation is reported UNVERIFIED and compensated, never assumed successful.
13. Record observed state, evidence and audit event. Release lock. Notify via Hermes.
```

**ARCH-040** Mutations are disabled in the current release. The policy engine denies every
non-read tool. The flow above is the specification that mutation work must implement; it is not a
claim of existing capability.

**ARCH-041** No operation may report success without read-back verification. "Command accepted"
is not success.

---

## 7. Trust boundaries

| ID | Boundary | Between | Assumption crossing it |
| --- | --- | --- | --- |
| **TB-1 / ARCH-050** | Public ingress | Zone P → Zone C | Caller is authenticated at the edge but **semantically untrusted**. Tool arguments are adversarial input. |
| **TB-2 / ARCH-051** | Internal control | Zone C → Zone W | Caller is the control plane only. Network-isolated. Requests carry no secrets. |
| **TB-3 / ARCH-052** | External content | Zone W ← Zone M | Rendered page content is **untrusted**. It may contain prompt-injection payloads and must never be treated as instructions. |
| **TB-4 / ARCH-053** | Notification egress | Zone C → Zone H | Only sanitized, redacted, low-detail events leave. Hermes is not authoritative. |
| **TB-5 / ARCH-054** | Personal/professional | Host personal environment ↔ Zone W profile | Hard boundary. See [docs/privacy-boundary.md](./privacy-boundary.md). |
| **TB-6 / ARCH-057** | Supply chain | Registry / PyPI / base images / CI → Zone C and Zone W | Untrusted until pinned by digest, scanned and gated. A dependency executes next to the professional profile. |
| **TB-7 / ARCH-058** | Application scope | Planner application ↔ Outlook application (reserved) | Applications share the control plane, the worker and the profile, but not their support state. Crossing this boundary is a *scope* decision, never an implicit consequence of code reuse. |

**ARCH-059 — Application boundary invariants (TB-7).** An application namespace may exist in the
repository, hold mock-backed implementation and be exercised by composites without becoming part
of the supported surface. The invariants are:

1. the public tool projection is registry-derived, and today is exactly the 17 Planner `READ`
   tools; a reserved application contributes **zero** public tools;
2. implementation state and live-support state are tracked separately, and a merge changes neither
   into a support claim (`mergeImpliesLiveSupport = false`);
3. cross-application composites (BATCH/DAG/runbooks) inherit the *most restrictive* state of the
   applications they touch and cannot upgrade a reserved application by aggregation;
4. promotion out of `RESERVED` requires live browser evidence in the target tenant, recorded
   against the capability — mock or synthetic evidence is never sufficient.

**ARCH-055** Data crossing TB-3 inbound is labelled `trust_level = untrusted_ui_derived` and
carries that label through state, evidence and tool output.

**ARCH-056** No component treats UI-derived text as a control instruction. Text extracted from
Planner is data, never a command, never a selector, never a policy input.

---

## 8. State store boundary

**ARCH-060** State lives in SQLite (`journal_mode=WAL`, `synchronous=FULL`, `foreign_keys=ON`,
`busy_timeout=30000`) owned exclusively by the control plane, on a dedicated volume. The worker
has no access to it.

**ARCH-061** The state store holds **control metadata only**:

| Table | Purpose |
| --- | --- |
| `schema_meta` | schema version |
| `resource` | desired vs observed state, keyed by stable `external_id` (+ `source_id`) |
| `resource_lock` | typed resource locks |
| `idempotency` | idempotency keys and result hashes |
| `saga` | long-running operation records |
| `checkpoint` | saga step checkpoints (FK → `saga`, cascade) |
| `approval` | approval records for `REQUIRE_APPROVAL` decisions, with consumption state |
| `audit_event` | append-only audit trail |

**ARCH-062** The state store **never** contains: passwords, cookies, bearer/refresh tokens,
storage state, session identifiers, raw DOM, screenshots containing content, or unredacted
personal data.

**ARCH-063** Planner *content* is not persisted in the current release. When caching is
introduced it requires an ADR, a retention rule, a redaction rule and an explicit privacy review.

**ARCH-064** The persistent browser profile is **not** part of the state store. It lives only in
the worker's volume and is a separate, higher-sensitivity asset.

---

## 9. Policy engine

**ARCH-070** The policy engine is a mandatory, non-bypassable gate evaluated in the control plane
before any worker call. Unknown tools are denied. Absence of an explicit allow is a denial.

**ARCH-071** Decisions: `ALLOW`, `DENY`, `REQUIRE_APPROVAL`. Inputs: tool identity, mutation
class, capability evidence, UIContract attestation state, runtime mode (`mock` / `live`),
configuration flags, target scope.

**ARCH-072** Mutation classes: `READ`, `SAFE_WRITE`, `GOVERNED_WRITE`, `DESTRUCTIVE`
(see [docs/security.md](./security.md) `SEC-020`). Every tool declares exactly one.

**ARCH-073** The policy engine is the only place where an operation becomes permissible. Tools do
not self-authorise; the worker does not authorise; Hermes does not authorise.

**ARCH-074** Policy evaluation is deterministic and side-effect free apart from audit emission.

---

## 10. UIContract registry

**ARCH-080** The UIContract is the single, centralized, versioned description of the Planner
Premium UI surface (`contracts/ui_contract.json`), packaged with the distribution.

**ARCH-081** Selectors are never fabricated. Unverified entries carry `status: UNVERIFIED_LIVE`
with a `null` value. A live operation against an unattested contract fails closed with
`UI_CONTRACT_UNATTESTED`.

**ARCH-082** A version mismatch between the control plane's registry and the worker's loaded
contract fails closed with `UI_DRIFT`.

**ARCH-083** Attestation is an evidence-backed governance event, not a code change. See
[docs/governance.md](./governance.md) `GOV-040`.

**ARCH-084** CI exercises the mock UI only. CI never touches a real Planner tenant.

---

## 11. Worker client

**ARCH-090** `planner_mcp.worker_client` is the sole egress abstraction to Zone W. It owns:
timeouts, bounded retries for **idempotent reads only**, circuit-breaking, error mapping to the
typed taxonomy, and response sanitisation.

**ARCH-091** The worker client refuses to transport secret material in either direction. Any
response field matching a credential/cookie/token shape is dropped and an audit event is raised.

**ARCH-092** Worker unavailability maps to `WORKER_UNAVAILABLE` and fails closed — never to a
degraded "assume success" path.

**ARCH-093** Retries are forbidden for any non-idempotent operation unless a read-back has proven
the prior attempt did not take effect (see `ARCH-041`, `SEC-040`).

---

## 12. Evidence and read-back path

**ARCH-100** Every capability claim is evidence-derived. Evidence sources: tenant context,
licence signals, UI observation, UIContract attestation state, runtime probe results. A capability
with no evidence is reported unknown/unsupported, never assumed.

**ARCH-101** Read-back is the verification primitive: after any state-changing step the worker
re-reads the target and the control plane compares observed state to the intended post-condition.

**ARCH-102** Read-back results are recorded as evidence with provenance (source, timestamp,
UIContract version, mode, trust level) and linked to the saga/checkpoint and audit event.

**ARCH-103** Evidence is redacted before storage and before exposure. Evidence never includes
screenshots of authenticated content, cookies, or identity material.

**ARCH-104** A capability is never declared "live supported" without recorded live evidence. See
[docs/governance.md](./governance.md) `GOV-090`.

---

## 13. Metrics and logging path

**ARCH-110** Logs are structured, JSON, redacted at the emission boundary by a central redaction
module. Redaction is applied before serialisation, not after.

**ARCH-111** Metrics are **low cardinality**. Permitted label dimensions: `tool`, `decision`,
`mutation_class`, `outcome`, `error_code`, `mode`. Forbidden as labels: plan IDs, task IDs, user
identifiers, tenant identifiers, e-mail addresses, URLs, free text.

**ARCH-112** Nothing on the telemetry path may carry secrets, cookies, passwords, session IDs,
tokens, or unredacted personal data — including in exception messages and stack traces.

**ARCH-113** Audit events are separate from operational logs: append-only, integrity-relevant, and
they record decision provenance (who/what/when/which policy/which approval).

**ARCH-114** Telemetry egress is opt-in per environment and must not carry Planner content.

---

## 14. Deployment boundaries

**ARCH-120** Two images, built and pinned by digest: control plane (`python:3.12-slim`-based) and
browser worker (official Playwright Python image). Base image pinning is a blocking CI gate.

**ARCH-121** Both containers run non-root with `no-new-privileges:true` and `cap_drop: [ALL]`.
The control plane runs a read-only root filesystem with tmpfs scratch. The worker requires a
writable profile directory (documented exception) and otherwise minimises writable surface.

**ARCH-122** No host Docker socket is mounted. No host home directory is mounted. No personal
browser profile directory is mounted. See [docs/privacy-boundary.md](./privacy-boundary.md)
`PRIV-050`.

**ARCH-123** Volumes: `browser-profile` (worker only, professional session) and `mcp-state`
(control plane only). They are never shared between services.

**ARCH-124** The two services are independently restartable. Worker restart must not lose the
professional session (persistent profile volume); control plane restart must not lose approvals,
locks or idempotency records (persistent state volume).

---

## 15. Failure posture

**ARCH-130** The system fails **closed** everywhere: unknown tool, unmatched policy, unattested
contract, drifted contract, unavailable worker, unverified read-back, Conditional Access blocker,
ambiguous tenant/account context.

**ARCH-131** `BLOCKER_CONDITIONAL_ACCESS` is terminal. The system stops and reports. No bypass,
no spoofing, no enrolment attempt, no alternative authentication path.

**ARCH-132** Partial application is never reported as success. Unverified outcomes are reported as
`UNVERIFIED` and compensated where a compensation exists.

---

## 16. Traceability

| ID range | Area |
| --- | --- |
| ARCH-001…009 | Scope and substrate |
| ARCH-010…015 | Component responsibilities |
| ARCH-020…023 | Public vs internal surface |
| ARCH-030…038 | Ports and network |
| ARCH-040…041 | Flows |
| ARCH-050…059 | Trust boundaries |
| ARCH-060…064 | State store |
| ARCH-070…074 | Policy engine |
| ARCH-080…084 | UIContract registry |
| ARCH-090…093 | Worker client |
| ARCH-100…104 | Evidence / read-back |
| ARCH-110…114 | Metrics / logging |
| ARCH-120…124 | Deployment |
| ARCH-130…132 | Failure posture |
