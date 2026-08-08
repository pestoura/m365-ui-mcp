# Threat Model

> **Document status:** Normative. **Method:** STRIDE per trust-zone boundary (zones defined in
> [architecture.md](architecture.md#5-trust-zones)), plus product-specific abuse cases. Every
> mitigation maps to a requirement ID in [traceability.md](traceability.md).
> **Companion docs:** [security.md](security.md), [privacy-boundary.md](privacy-boundary.md),
> [idempotency.md](idempotency.md), [governance.md](governance.md).

Method: STRIDE per trust-zone boundary (zones defined in [architecture.md](architecture.md#5-trust-zones)),
plus product-specific abuse cases. Every mitigation maps to a requirement ID in
[traceability.md](traceability.md).

## 0. Methodology and assumptions

- **STRIDE** per boundary: **S**poofing, **T**ampering, **R**epudiation, **I**nformation
  disclosure, **D**enial of service, **E**levation of privilege.
- **Trust zones** (from [architecture.md](architecture.md#5-trust-zones)): E (edge/public),
  C (control), W (execution/worker+profile), H (human). Hermes attaches to C out of band.
- **Assumptions:** the human is trusted with their own identity but may be fatigued or deceived;
  the MCP client is untrusted by default; the public internet is hostile; the tenant is outside
  our control; the personal host must stay personal.
- **Coverage rule:** every asset has at least one threat; every threat has a mitigation that maps
  to a `SEC-*`/`T*`/`P*` requirement ID; every residual risk is explicitly accepted with a
  compensating control and a review trigger.

## 1. Assets

| ID | Asset | Impact if compromised |
| --- | --- | --- |
| A1 | Authenticated professional browser session | Full impersonation in tenant |
| A2 | Professional password | Account takeover, tenant-wide |
| A3 | MFA approval channel | Bypass of second factor |
| A4 | Project data (plans, tasks, people, goals) | Confidentiality/integrity loss |
| A5 | Approval ledger | Governance bypass, replay |
| A6 | Evidence/logs | Data leak via artefacts |
| A7 | Personal device integrity/privacy | Corporate control of a personal machine |

### 1.1 Asset classification

| Asset | Data class | At rest | In transit | Confidentiality | Integrity | Availability |
| --- | --- | --- | --- | --- | --- | --- |
| A1 session | Secret (ephemeral) | Profile volume only (`0700`) | Internal network only | High | High | Medium |
| A2 password | Secret (never stored) | Nowhere | Human → Microsoft page only | Critical | n/a | n/a |
| A3 MFA | Secret (human-held) | Authenticator app | Microsoft channel only | Critical | High | Medium |
| A4 project | Confidential tenant | State store (ids/hashes) | Sanitized output only | High | High | Medium |
| A5 ledger | Governance | State store | Internal | High | Critical | High |
| A6 evidence | Internal | Local evidence store | By hash ref only | Medium | High | Low |
| A7 device | Personal | Host OS | n/a | Critical | Critical | High |

## 2. Boundaries

- **B1** MCP client -> Cloudflare Portal
- **B2** Portal -> control plane
- **B3** Control plane -> worker
- **B4** Worker -> Chromium/Planner UI
- **B5** Control plane -> Hermes
- **B6** Human -> Authenticator

### 2.1 Boundary data flows

| Boundary | Direction | Carries | Trust change |
| --- | --- | --- | --- |
| B1 | client → portal | MCP request, client identity | Untrusted → edge-identified |
| B2 | portal → control | authenticated request, no tenant data | edge → control logic |
| B3 | control → worker | semantic operation envelope | control → execution (private RPC) |
| B4 | worker → UI | UI actions under UIContract | execution → tenant system of record |
| B5 | control → Hermes | sanitized HITL payload / notifications | control → out-of-band (one-way) |
| B6 | human → Authenticator | MFA approval | human → tenant (never software) |

Traffic is only ever E → C → W. W never calls out to E. Hermes attaches to C only and cannot call
back into W. This directional invariant is itself a control (SEC-010, SEC-013).

## 3. STRIDE

| # | Boundary | Threat (STRIDE) | Mitigation |
| --- | --- | --- | --- |
| T1 | B1 | **S** Unauthorized client impersonates operator | Portal-enforced client identity; no anonymous exposure; deny by default |
| T2 | B2 | **T** Request tampering / tool-name injection | Strict schema validation; allow-list of registered tools; reject unknown fields |
| T3 | B3 | **E** MCP caller reaches raw browser primitives | Raw input primitives are not exposed at any layer; worker API is semantic-only ([ADR-001](adr/ADR-001-browser-automation.md)) |
| T4 | B3 | **E** Worker publicly routable | Worker binds private interface only; no ingress route; portal cannot address it |
| T5 | B4 | **T** UI drift causes wrong element mutation | UIContract attestation required pre-interaction; fail closed on selector uncertainty |
| T6 | B4 | **R** No proof of what was changed | Mandatory read-back + evidence artefact per mutation |
| T7 | B5 | **I** Secret/PII leakage into notifications | Sanitized payload allow-list; MFA payload restricted to `operation_id`, `service`, `description`, `number`, `expiry` |
| T8 | B5/B6 | **E** Hermes used to approve MFA | Architecturally forbidden; approval only in Microsoft Authenticator ([ADR-004](adr/ADR-004-human-in-loop-mfa.md)) |
| T9 | any | **I** Password persisted | Password never in repo/env/MCP/Hermes/log/state; typed by human into the browser only |
| T10 | control | **E** Approval replay | Approvals persistent and non-replayable, bound to `operation_id` + payload hash |
| T11 | control | **T** Duplicate mutation on retry | Idempotency keys + read-back-before-retry ([idempotency.md](idempotency.md)) |
| T12 | worker | **D** Session lock starvation / concurrent profile use | Single-owner profile, scoped locks, timeouts, circuit breaker |
| T13 | logs | **I** DOM evidence contains personal data | Redaction pipeline before persistence; low-cardinality metrics only |
| T14 | device | **E** Conditional Access forces enrolment | `BLOCKER_CONDITIONAL_ACCESS`, hard stop, no bypass, no spoofed device state ([ADR-008](adr/ADR-008-personal-device-privacy-boundary.md)) |
| T15 | B4 | **S** Phishing / look-alike login surface | Origin allow-list before any credential surface is shown to the human |
| T16 | control | **R** Capability over-claim | Support state derived only from attestation records; `UNVERIFIED_LIVE` is the default |

### 3.1 Extended threat register (per boundary)

| # | Boundary | Threat (STRIDE) | Mitigation | Req ID |
| --- | --- | --- | --- | --- |
| T17 | B1 | **D** Client floods portal / exhaustion | Portal rate limiting + edge identity throttling | SEC-011 |
| T18 | B2 | **T** Replay of a captured request | Per-request auth + short-lived tunnel; no replayable token at B2 | SEC-025 |
| T19 | B3 | **I** Worker egress to non-Microsoft host | Egress allow-list to Microsoft endpoints only (SEC-087) | SEC-087 |
| T20 | B3 | **D** Control plane calls worker after worker unhealthy | Health probe; `CIRCUIT_OPEN` fast-fail (SEC-066) | SEC-066 |
| T21 | B4 | **T** Stale selector mutates wrong row after UI change | Drift detection on every interaction; `UI_DRIFT` fail closed | SEC-060 |
| T22 | B4 | **E** Worker escalates to OS-level action | `cap_drop: ALL`, read-only rootfs, no-new-privileges | SEC-081/82 |
| T23 | B5 | **R** Hermes payload misused to infer tenant data | Allow-list fields; no task text/title/UPN | SEC-031/73 |
| T24 | B6 | **S** MFA-fatigue against the human | Single sanitized number event; hard `WAITING_FOR_MFA` timeout → `AUTH_FAILED` | SEC-033/34 |
| T25 | control | **T** Policy engine fails open | Policy load failure → `DENY` everything except `planner_health` | SEC-064 |
| T26 | control | **E** Auth state machine advanced without human | `AUTHENTICATED` requires human sign-in; software cannot set it | SEC-063 |
| T27 | worker | **I** Profile volume copied off host | Profile never exported; `0700`; excluded from backups/git | SEC-012 |
| T28 | logs | **I** Error string leaks token/URL | Sanitized client errors; redaction deny-list | SEC-071/75 |

## 4. Attack trees (top risks)

### 4.1 Session impersonation (asset A1)

```
Goal: act as the professional user in the tenant
 ├─ [S] Steal the session cookie (A1)
 │   ├─ Exfiltrate profile volume        → blocked: SEC-012, no export, 0700
 │   ├─ Read it from logs/metrics        → blocked: SEC-071 deny-list, SEC-073 cardinality
 │   └─ Sniff B3/B4 traffic             → blocked: internal network, TLS, no egress (SEC-087)
 ├─ [E] Reach raw browser from MCP      → blocked: T3, ADR-001 semantic-only
 └─ [S] Spoof client at B1              → blocked: T1 portal identity, deny-by-default
```

### 4.2 Capability laundering (asset A5 / AC1)

```
Goal: expose a capability as SUPPORTED without evidence
 ├─ Author support_level by hand        → blocked: T16, computed from ledger
 ├─ Forge attestation record            → blocked: append-only ledger, hash-chained
 └─ Skip read-back on mutation          → blocked: READ_BACK_OK terminal only (state-model)
```

## 5. Abuse cases

- **AC1 Capability laundering** — an operator marks a capability `SUPPORTED` without evidence.
  Control: support state is computed from the attestation ledger, not authored by hand;
  matrix rows without evidence stay `UNVERIFIED_LIVE` ([planner-premium-capabilities.md](planner-premium-capabilities.md)).
- **AC2 Silent destructive change** — a `DESTRUCTIVE` operation slips through as `SAFE_WRITE`.
  Control: `mutation_class` is declared in the manifest, policy is keyed on it, and destructive
  operations always require approval and produce compensation plans.
- **AC3 Device coercion drift** — a Microsoft prompt offers "register this device". Control:
  worker treats enrolment prompts as a blocker state and never accepts.
- **AC4 Session ambiguity exploitation** — acting while auth state is `UNKNOWN`.
  Control: readiness gate requires `AUTHENTICATED`.

### 5.1 Abuse-case detail

| AC | Pre-condition | Attack | Detection | Control |
| --- | --- | --- | --- | --- |
| AC1 | operator can write matrix | mark row `SUPPORTED` | support_level computed, not read from doc | T16, governance attestation rule |
| AC2 | manifest mis-classified | ship destructive as safe | policy keyed on `mutation_class`; tests assert mapping | SEC-052, governance |
| AC3 | CA prompt appears | click "register" | enrolment UI → `BLOCKER_CONDITIONAL_ACCESS` | PR-1, SEC-041 |
| AC4 | auth `UNKNOWN` | issue tenant op | readiness gate requires `AUTHENTICATED` | SEC-063 |

## 6. Adversary personas

| Persona | Capability | What stops them |
| --- | --- | --- |
| Rogue MCP client | can send crafted MCP requests | T1, T2, SEC-050 default-deny |
| Network attacker | can observe public internet | TLS, no tenant data at B1/B2, sanitised output |
| Compromised dependency | can execute in container | `cap_drop`, read-only rootfs, egress allow-list |
| Deceived human | can be MFA-fatigued | single number event, hard timeout, human-only approval |
| Tenant admin (hostile CA) | can demand managed device | `BLOCKER_CONDITIONAL_ACCESS`, no enrolment |

## 7. Defense-in-depth layers

| Layer | Covers | Primary controls |
| --- | --- | --- |
| Edge | B1 | client identity, rate limit, deny-by-default |
| Policy | B2/C | schema validation, tool allow-list, default-deny, approvals |
| Execution | B3/W | semantic-only API, private network, health-gated calls |
| UI | B4 | UIContract attestation, origin allow-list, read-back |
| Out-of-band | B5 | sanitized payload allow-list, one-way Hermes |
| Human | B6 | MFA in Authenticator only, hard timeout |
| Device | host | privacy-boundary prohibitions, container hardening |
| Evidence | logs | redaction, cardinality, hash-referenced artefacts |

## 8. Control → requirement mapping

Every threat above maps to a stable requirement ID (full text in
[security.md](security.md) / [traceability.md](traceability.md)):

- Spoofing (S): T1→SEC-011, T15→origin allow-list, T17→rate limit, T24→SEC-033, T28→SEC-075.
- Tampering (T): T2→schema allow-list, T5/T21→SEC-060, T10/T11→idempotency+approval, T18→SEC-025.
- Repudiation (R): T6→read-back, T16→T16, T23→SEC-031.
- Information disclosure (I): T7→SEC-031, T9→SEC-020/21, T13→SEC-070, T19→SEC-087, T27→SEC-012.
- Denial of service (D): T12→locks/circuit, T17→rate limit, T20→SEC-066.
- Elevation (E): T3→ADR-001, T4→SEC-010, T8→ADR-004, T14→SEC-041, T22→SEC-081/82, T26→SEC-063.

## 9. Verification mapping

| Threat | Verified by |
| --- | --- |
| T1, T2 | portal identity test; schema-allowlist fuzz test |
| T3, T4 | tool surface test (no raw primitives); network egress test |
| T5, T21 | mock-UI drift test → `UI_DRIFT` |
| T6 | read-back required test; `READ_BACK_OK` terminal test |
| T7, T23 | sanitized-payload test; redaction unit test |
| T8 | architecture test: Hermes cannot approve (no code path) |
| T9 | secret-scan + code-absence (no password read path) |
| T10 | approval replay test (single-use, fingerprint-bound) |
| T11 | duplicate-request suppression test |
| T12 | concurrency/lock test; circuit-breaker test |
| T13, T27 | redaction test; profile-export refusal test |
| T14 | enrolment-prompt test → `BLOCKER_CONDITIONAL_ACCESS` |
| T15 | origin allow-list test before credential surface |
| T16 | support_level computed-from-ledger test |
| T24 | MFA-fatigue timeout test |
| T25 | policy-load-failure → DENY test |
| T26 | auth-state-machine test (software cannot set AUTHENTICATED) |

## 10. Residual risks (accepted for A1)

| ID | Risk | Why accepted | Compensating control |
| --- | --- | --- | --- |
| R1 | UI automation is inherently brittle | Premium capability is not otherwise reachable | UIContract + fail closed + drift metrics |
| R2 | Live session on a personal host is high value | Human owns the identity by design | Isolated profile, no personal browsing, revocation runbook |
| R3 | Tenant policy may make the product unusable | Out of our control | Explicit `BLOCKED_CONDITIONAL_ACCESS` / `UNSUPPORTED_TENANT` states |

### 10.1 Residual-risk review triggers

| Risk | Re-open if | Action |
| --- | --- | --- |
| R1 | UI drift rate exceeds threshold in observability | tighten attestation, add contract fragments |
| R2 | A personal-browsing path is found in the profile | privacy-boundary incident response (§9) |
| R3 | A tenant becomes usable after a policy change | re-run attestation; advance capability states by evidence |

## 11. References

- [architecture.md](architecture.md#5-trust-zones) — trust zones E/C/W/H.
- [security.md](security.md) — SEC-* objectives and controls.
- [privacy-boundary.md](privacy-boundary.md) — device prohibitions (asset A7).
- [idempotency.md](idempotency.md) — T10/T11 controls.
- [governance.md](governance.md) — policy, approvals, blockers.
- [ADR-001](adr/ADR-001-browser-automation.md), [ADR-004](adr/ADR-004-human-in-loop-mfa.md),
  [ADR-006](adr/ADR-006-graph-not-a-functional-gate.md),
  [ADR-008](adr/ADR-008-personal-device-privacy-boundary.md).
