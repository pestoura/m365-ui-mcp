# Planner MCP — Threat Model

Status: specification (implementation-grade)
Canonical upstream: [docs/vision.md](./vision.md)
Related: [docs/architecture.md](./architecture.md) · [docs/security.md](./security.md) · [docs/privacy-boundary.md](./privacy-boundary.md) · [docs/governance.md](./governance.md)

Threat IDs (`THR-xxx`) are stable. Controls reference `SEC-xxx`, `ARCH-xxx`, `PRIV-xxx`, `GOV-xxx`.
Residual risk is stated honestly: where a control is **planned but not implemented**, it is marked
`PLANNED` and the residual risk is *not* reduced.

---

## 1. Assets

| ID | Asset | Why it matters | Sensitivity |
| --- | --- | --- | --- |
| **A-01** | Persistent professional Chromium profile (cookies, storage state, session) | Full impersonation of the operator inside the tenant | Critical |
| **A-02** | Microsoft account password | Account takeover, MFA-reset pivot | Critical — never present in-system (`PRIV-070`) |
| **A-03** | Planner Premium business data (plans, tasks, assignments, dates, goals) | Confidentiality, integrity of work planning | High |
| **A-04** | Control-plane state DB (approvals, locks, idempotency, sagas, audit) | Integrity of authorisation and of mutation safety | High |
| **A-05** | Approval records | Authorisation tokens for governed mutations | High |
| **A-06** | UIContract (selectors + attestation state) | Determines what the browser touches | High |
| **A-07** | Audit/evidence trail | Accountability, incident reconstruction | High |
| **A-08** | Operational logs and metrics | Leak channel if unredacted | Medium |
| **A-09** | Container images, dependencies, CI pipeline | Supply-chain foothold into A-01 | Critical |
| **A-10** | Cloudflare portal configuration and edge credentials | Ingress authorisation | Critical |
| **A-11** | Hermes notification channel | Social-engineering / approval-manipulation surface | Medium-High |
| **A-12** | Host personal environment (personal profiles, files, device identity) | Privacy boundary; out of scope for automation | Critical — must remain untouched (`PRIV-001`) |

---

## 2. Trust boundaries

Defined in [docs/architecture.md](./architecture.md) §7. Restated for threat enumeration:

| Boundary | Crossing | Adversarial assumption |
| --- | --- | --- |
| **TB-1** | MCP client / Cloudflare portal → control plane | Tool arguments are attacker-controlled; the caller may be a compromised or manipulated agent |
| **TB-2** | Control plane → browser worker | Only legitimate caller; but a compromised control plane fully drives the browser |
| **TB-3** | Microsoft UI → browser worker | Rendered content is hostile input (prompt injection, spoofed UI, drifted DOM) |
| **TB-4** | Control plane → Hermes | Outbound sanitized events; inbound human decisions must be authenticated and non-replayable |
| **TB-5** | Professional worker context ↔ personal host environment | Hard separation; any crossing is a privacy incident |
| **TB-6** | Supply chain (registry, PyPI, base images, CI) → both services | Untrusted until pinned, scanned and gated |

---

## 3. Actors

| ID | Actor | Motivation / capability |
| --- | --- | --- |
| **AC-1** | Legitimate operator (Pedro) | Wants safe, reversible, auditable automation |
| **AC-2** | Legitimate MCP client (ChatGPT) | May be *manipulated* by content it reads; not malicious by design |
| **AC-3** | External attacker via public ingress | Reaches the portal; attempts authn bypass, tool abuse, enumeration |
| **AC-4** | Prompt-injection content author | Plants instructions inside Planner tasks/comments/plan names |
| **AC-5** | Malicious/compromised dependency or base image | Code execution inside a container |
| **AC-6** | Local host attacker / malware on the host | Reads volumes, Docker socket, profile directory |
| **AC-7** | Insider with repo/CI write access | Alters policy, selectors, gates |
| **AC-8** | Microsoft-side change (non-adversarial) | UI drift, CA policy change, licensing change — breaks assumptions silently |
| **AC-9** | Confused deputy: the agent itself | Uses legitimate privilege on behalf of an illegitimate instruction |

---

## 4. STRIDE analysis by surface

Legend for **Status**: `IMPLEMENTED` (control exists today), `PARTIAL`, `PLANNED` (specified only).

### 4.1 MCP ingress (Cloudflare portal → control plane) — TB-1

| ID | STRIDE | Threat | Controls | Status | Residual risk |
| --- | --- | --- | --- | --- | --- |
| **THR-001** | Spoofing | Unauthenticated caller reaches the MCP endpoint directly, bypassing the portal | Control plane bound to loopback (`ARCH-037`); reached only via the Cloudflare connector; no public bind | PARTIAL | If the host is misconfigured or another local process proxies the port, ingress authn is bypassed. Control-plane-level caller authentication is `PLANNED` (`SEC-071`). **Medium.** |
| **THR-002** | Tampering | Tool arguments crafted to reach unintended plans/tasks/tenants | Strict argument schemas; policy engine target-scope evaluation (`ARCH-071`); selectors never caller-supplied (`ARCH-023`) | PARTIAL | Scope pinning per tenant is `PLANNED`. **Medium.** |
| **THR-003** | Repudiation | Caller denies having requested an operation | Append-only `audit_event` with decision provenance (`ARCH-113`) plus edge logs | PARTIAL | Audit integrity protection (signing/append-only storage) is `PLANNED`. **Medium.** |
| **THR-004** | Information disclosure | Enumeration of plans/tenants through error messages | Typed error taxonomy with stable codes and no content echo; redaction at emission (`ARCH-110`) | IMPLEMENTED | Timing/oracle differences remain. **Low.** |
| **THR-005** | Denial of service | Request flood exhausts browser worker | Edge rate limiting; single-flight locking; bounded timeouts; circuit breaker (`ARCH-090`) | PARTIAL | Browser is inherently a scarce resource; a permitted caller can still saturate it. **Medium.** |
| **THR-006** | Elevation of privilege | Escape-hatch/raw tool exposed on the public surface | Semantic-only surface (`ARCH-020`); raw primitives internal (`ARCH-021`); escape hatches require ADR + governance (`ARCH-022`) | IMPLEMENTED | Depends on review discipline. **Low-Medium.** |

### 4.2 Control plane — Zone C

| ID | STRIDE | Threat | Controls | Status | Residual risk |
| --- | --- | --- | --- | --- | --- |
| **THR-010** | Elevation | Policy engine bypassed by a tool calling the worker client directly | Single egress abstraction (`ARCH-015`, `ARCH-090`); policy evaluated before egress (`ARCH-070`) | PARTIAL | Enforced by structure and review; an automated architectural test is `PLANNED`. **Medium.** |
| **THR-011** | Tampering | Configuration flipped to enable mutations without governance (`PLANNER_ALLOW_MUTATIONS`) | Fail-closed defaults (`SEC-001`); mutation enablement is a governed release gate (`GOV-030`) | PARTIAL | Anyone with environment control can flip the flag. Mitigated only by the fact that mutating tools do not yet exist. **Medium.** |
| **THR-012** | Repudiation | Decision history rewritten | Append-only audit table; separate from operational logs | PARTIAL | No cryptographic chaining yet (`PLANNED`, `SEC-090`). **Medium.** |
| **THR-013** | Information disclosure | Exception messages/stack traces leak content or identity | Central redaction applied before serialisation (`ARCH-110`, `ARCH-112`) | IMPLEMENTED | Third-party library logs may bypass the wrapper. **Low-Medium.** |
| **THR-014** | Denial of service | State DB lock contention stalls all operations | WAL, `busy_timeout=30000`, typed locks with expiry | PARTIAL | Long-held locks after a crash need a reaper (`PLANNED`). **Medium.** |

### 4.3 State database — A-04

| ID | STRIDE | Threat | Controls | Status | Residual risk |
| --- | --- | --- | --- | --- | --- |
| **THR-020** | Tampering | Direct SQLite edit forges an approval or clears an idempotency record | Dedicated volume, non-root container, no host home mount (`ARCH-122`); approvals bound to a request digest (`SEC-030`) | PARTIAL | A host-level attacker (AC-6) with volume access can rewrite state. Encryption/MAC of approval rows is `PLANNED`. **Medium-High.** |
| **THR-021** | Information disclosure | State DB exfiltrated | No credentials, no cookies, no Planner content stored (`ARCH-062`, `ARCH-063`) | IMPLEMENTED | Metadata (external IDs, operation history) still leaks. **Low-Medium.** |
| **THR-022** | Tampering | Idempotency record collision causes a wrong cached result to be returned | Keys include tool identity, target `external_id`, argument digest and schema version | PLANNED | Until implemented, no idempotency protection exists. **Medium** (no mutations today). |

### 4.4 Browser worker — Zone W

| ID | STRIDE | Threat | Controls | Status | Residual risk |
| --- | --- | --- | --- | --- | --- |
| **THR-030** | Spoofing | Something other than the control plane calls the worker | Internal-only Docker network (`internal: true`), no published port (`ARCH-035`) | IMPLEMENTED | Any container attached to that network can call it. Request authentication (HMAC, `SEC-070`) is `PLANNED`. **Medium.** |
| **THR-031** | Elevation | Browser escape → container → host | Non-root, `no-new-privileges`, `cap_drop: ALL`, tmpfs `/tmp` and `/dev/shm`, no Docker socket (`SEC-100`…`SEC-104`) | IMPLEMENTED | Chromium sandbox + container is not a hypervisor boundary; a 0-day escape reaches the container with the profile. Worker rootfs is writable (profile requirement). **Medium.** |
| **THR-032** | Information disclosure | Worker returns raw DOM/screenshots containing authenticated content | Structured sanitized responses; worker client drops credential-shaped fields (`ARCH-091`); no screenshots of authenticated content in evidence (`ARCH-103`) | PARTIAL | Debug/diagnostic paths are the likely leak. **Medium.** |
| **THR-033** | Tampering | Worker executes an action the control plane did not intend | Actions derive from UIContract selectors only (`ARCH-023`); read-back verification (`ARCH-101`) | PARTIAL | Read-back is specified; mutation paths not yet built. **Medium.** |
| **THR-034** | Denial of service | Chromium hangs/leaks and wedges the session | Timeouts, circuit breaker, restart policy, persistent profile survives restart (`ARCH-124`) | PARTIAL | A wedged auth state may need human re-auth. **Low-Medium.** |

### 4.5 Chromium persistent profile — A-01

| ID | STRIDE | Threat | Controls | Status | Residual risk |
| --- | --- | --- | --- | --- | --- |
| **THR-040** | Information disclosure | Profile exfiltration (cookies/storage state) = full session theft | Profile confined to a named volume, worker-only (`ARCH-013`, `ARCH-123`); never in repo, backups, logs or state (`SEC-002`); `.gitignore` excludes `profiles/` | PARTIAL | Host root or Docker-daemon access reads the volume directly. Volume encryption is `PLANNED`. **High** — this is the single highest-value asset. |
| **THR-041** | Tampering | Malicious extension or injected profile artefact | No extensions installed; profile provisioned only by the worker | PARTIAL | No integrity attestation of profile contents. **Medium.** |
| **THR-042** | Spoofing | Personal profile reused for professional automation (or vice versa) | Hard separation (`PRIV-030`…`PRIV-034`); no host home or personal profile mounts (`PRIV-050`) | IMPLEMENTED | Depends on deployment discipline; enforced by compose review. **Low-Medium.** |
| **THR-043** | Information disclosure | Profile copied out for "debugging" | Prohibited by policy (`PRIV-052`); no host path mounts | PARTIAL | Human process control only. **Medium.** |

### 4.6 Microsoft session, MFA, Conditional Access

| ID | STRIDE | Threat | Controls | Status | Residual risk |
| --- | --- | --- | --- | --- | --- |
| **THR-050** | Spoofing | MFA fatigue / phishing: attacker triggers approvals the operator accepts | MFA satisfied only in Microsoft Authenticator (`SEC-060`); the system never renders, proxies or asks for MFA codes; only sanitized metadata surfaces | IMPLEMENTED | Human remains the decision point; fatigue attacks are not eliminated. **Medium.** |
| **THR-051** | Information disclosure | Password captured or transported | Password is never stored, transported, logged, env-injected or requested via MCP/Hermes/repo (`PRIV-070`); authentication is interactive, human-driven, into the persistent profile | IMPLEMENTED | Host-level keylogging is out of scope. **Low.** |
| **THR-052** | Elevation | Conditional Access "compliant device" requirement drives a bypass attempt (enrolment, device-cert install, UA/device spoofing) | `BLOCKER_CONDITIONAL_ACCESS` is terminal (`ARCH-131`, `PRIV-020`); enrolment forbidden (`PRIV-010`); spoofing forbidden (`PRIV-022`) | IMPLEMENTED | Organisational pressure to "just make it work" is the real risk; governance must hold the line. **Low (technical) / Medium (process).** |
| **THR-053** | Spoofing | Tenant/account confusion: acting in the wrong tenant or as the wrong identity | Sanitized account context surfaced (`tenant_display`, `account_kind`, `profile`); ambiguity fails closed (`ARCH-130`) | PARTIAL | Explicit tenant pinning with a configured expected tenant is `PLANNED`. **Medium-High** for multi-tenant/multi-account operators. |
| **THR-054** | Tampering | Session hijack via stolen cookies from A-01 | See THR-040 | PARTIAL | Inherits THR-040 residual. **High.** |

### 4.7 UI selectors and drift — A-06

| ID | STRIDE | Threat | Controls | Status | Residual risk |
| --- | --- | --- | --- | --- | --- |
| **THR-060** | Tampering | Selector hijack: a malicious/renamed element matches a selector, so the action hits the wrong control | Centralized versioned UIContract (`ARCH-080`); no fabricated selectors (`ARCH-081`); read-back verification before declaring success (`ARCH-101`) | PARTIAL | Read-back protects mutations; reads can still bind to the wrong element. Strict, semantic, role-based selectors are `PLANNED`. **Medium.** |
| **THR-061** | Tampering | Silent UI drift changes semantics without breaking the selector | Version match required, `UI_DRIFT` fail-closed (`ARCH-082`); attestation campaigns (`GOV-040`) | PARTIAL | Drift that keeps the selector valid but changes meaning is not automatically detectable. **Medium-High.** |
| **THR-062** | Spoofing | Attacker-controlled page content mimics Planner UI to trigger unintended interaction | Navigation restricted to expected Planner origins; untrusted content labelling (`ARCH-055`) | PLANNED | Origin allow-listing not yet enforced in code. **Medium.** |
| **THR-063** | Elevation | Caller supplies a selector or XPath through a tool argument | Selectors never accepted from callers (`ARCH-023`) | IMPLEMENTED | Requires schema discipline on new tools. **Low.** |

### 4.8 Prompt/tool abuse and confused deputy

| ID | STRIDE | Threat | Controls | Status | Residual risk |
| --- | --- | --- | --- | --- | --- |
| **THR-070** | Elevation | Prompt injection inside a Planner task/comment instructs the agent to perform destructive actions | UI-derived data labelled `untrusted_ui_derived` and never treated as instruction (`ARCH-055`, `ARCH-056`); destructive classes require approval (`SEC-020`); mutations disabled today | PARTIAL | The MCP client is outside our control; if it obeys injected text it will call our tools. Our defence is policy + approval, not client behaviour. **Medium-High.** |
| **THR-071** | Elevation | Confused deputy: legitimate agent privilege used for an illegitimate instruction | Policy engine is the sole authoriser (`ARCH-073`); `GOVERNED_WRITE`/`DESTRUCTIVE` require human approval bound to a request digest (`SEC-030`) | PARTIAL | Human approves what is shown; if the summary is misleading, approval is misinformed. Approval prompts must show intent + target + diff (`PLANNED`, `SEC-034`). **Medium-High.** |
| **THR-072** | Tampering | Tool-argument smuggling: raw UI primitives hidden in a semantic argument (pass-through fields) | Strict closed schemas; no pass-through/opaque fields (`ARCH-021`) | PARTIAL | Requires schema review on every new tool. **Medium.** |
| **THR-073** | Elevation | Chained low-risk operations aggregate into a high-risk outcome | Mutation classification per operation; saga-level review; rate limits | PLANNED | Aggregate-risk detection does not exist. **Medium.** |

### 4.9 Approvals, replay, duplication, races

| ID | STRIDE | Threat | Controls | Status | Residual risk |
| --- | --- | --- | --- | --- | --- |
| **THR-080** | Elevation | Replayed approval: an old approval reused for a new operation | Approvals are persistent, single-use, atomically consumed, digest-bound, time-limited (`SEC-030`…`SEC-033`) | PLANNED | Approval table exists; consumption semantics not yet implemented. **Medium** (no mutations today). |
| **THR-081** | Tampering | Duplicate mutation from a retried request | Idempotency keys + result hashes; read-back before retry; retries forbidden for non-idempotent ops (`ARCH-093`, `SEC-040`) | PLANNED | Not yet implemented. **Medium.** |
| **THR-082** | Tampering | Race condition: two concurrent operations mutate the same resource | Typed resource locks per `external_id`; single-flight per resource (`ARCH-061`) | PARTIAL | Lock table exists; acquisition/expiry semantics not yet enforced end-to-end. **Medium.** |
| **THR-083** | Repudiation | Approval attributed to the wrong human | Approval records carry approver identity, channel and timestamp | PLANNED | Hermes channel identity binding not implemented. **Medium.** |

### 4.10 Cloudflare portal — A-10

| ID | STRIDE | Threat | Controls | Status | Residual risk |
| --- | --- | --- | --- | --- | --- |
| **THR-090** | Spoofing | Portal misconfiguration exposes the MCP surface without authentication | Portal is the authentication boundary; configuration is change-controlled (`GOV-050`) | PARTIAL | No automated configuration drift check. Defence in depth at the control plane is `PLANNED` (`SEC-071`). **Medium-High.** |
| **THR-091** | Information disclosure | Edge logs capture tool arguments containing business data | Arguments kept semantic and minimal; no content in tool arguments where avoidable | PARTIAL | Edge logging is outside our redaction pipeline. **Medium.** |
| **THR-092** | Elevation | Compromise of the Cloudflare API token used to manage the tunnel/portal | Tokens live only in the operator's secret store, never in the repo, never in logs (`SEC-050`) | IMPLEMENTED | Token scope must be minimal; scope review is a governance item. **Medium.** |
| **THR-093** | Denial of service | Portal/tunnel outage removes all access | Documented degraded posture: fail closed, no alternative unauthenticated path | IMPLEMENTED | Availability loss accepted by design. **Low.** |

### 4.11 Hermes notifications — A-11

| ID | STRIDE | Threat | Controls | Status | Residual risk |
| --- | --- | --- | --- | --- | --- |
| **THR-100** | Information disclosure | Notification payload leaks Planner content or identity into a chat channel | Sanitized, redacted, minimal events only (`ARCH-114`, `TB-4`) | PARTIAL | Notification templates must be reviewed per event type. **Medium.** |
| **THR-101** | Spoofing | Forged "approved" message injected into the notification channel | Approvals are authoritative only in the control-plane state store; Hermes conveys, it does not decide (`ARCH-014`) | PARTIAL | Binding of a channel message to an approval record is `PLANNED`. **Medium-High.** |
| **THR-102** | Elevation | Hermes compromise used to drive Planner operations | Hermes is out of the execution path and has no worker access (`ARCH-004`) | IMPLEMENTED | Hermes can still influence a human via misleading prompts. **Medium.** |
| **THR-103** | Repudiation | No record of which notification led to which decision | Audit event links approval ↔ notification reference | PLANNED | **Medium.** |

### 4.12 Logs, metrics, evidence — A-07, A-08

| ID | STRIDE | Threat | Controls | Status | Residual risk |
| --- | --- | --- | --- | --- | --- |
| **THR-110** | Information disclosure | Secrets/cookies/session IDs written to logs | Central redaction before serialisation; explicit deny-list of secret shapes (`SEC-050`, `ARCH-112`) | IMPLEMENTED | Novel secret shapes may evade the deny-list. **Low-Medium.** |
| **THR-111** | Information disclosure | High-cardinality metric labels leak identifiers | Low-cardinality label allow-list (`ARCH-111`, `SEC-052`) | IMPLEMENTED | Requires review of every new metric. **Low.** |
| **THR-112** | Tampering | Evidence altered after the fact to justify a support claim | Evidence is provenance-tagged and append-only; support claims require recorded evidence (`GOV-090`) | PARTIAL | No cryptographic integrity yet. **Medium.** |
| **THR-113** | Information disclosure | Screenshots as evidence capture authenticated content | Screenshots of authenticated content are excluded from evidence (`ARCH-103`) | IMPLEMENTED | Debug tooling could reintroduce them. **Low-Medium.** |

### 4.13 CI and supply chain — A-09, TB-6

| ID | STRIDE | Threat | Controls | Status | Residual risk |
| --- | --- | --- | --- | --- | --- |
| **THR-120** | Tampering | Malicious dependency executes inside the worker container, next to the profile | Pinned dependencies, dependency scanning, Trivy CRITICAL/HIGH gate, CycloneDX SBOM per image (`SEC-110`…`SEC-113`) | PARTIAL | Scanners detect known CVEs, not novel malicious packages. **Medium-High.** |
| **THR-121** | Tampering | Base image swapped (tag mutation) | Both base images pinned by digest; a blocking CI gate fails the build if a digest is lost | IMPLEMENTED | Digest updates must be reviewed deliberately. **Low.** |
| **THR-122** | Elevation | CI secrets exfiltrated by a malicious PR workflow | CI never touches a real tenant (`ARCH-084`); no live credentials in CI; mock mode only | IMPLEMENTED | Repo/CI write access (AC-7) remains a full compromise path. **Medium.** |
| **THR-123** | Tampering | Insider changes policy, selectors or gates | Change control, review, ADR requirement for policy/mutation changes (`GOV-020`, `GOV-030`) | PARTIAL | Single-maintainer projects cannot enforce four-eyes. **Medium-High** — explicitly accepted. |
| **THR-124** | Information disclosure | Secret committed to the repo | Secret scanning in CI; `.gitignore` for profiles/state/artifacts; documented prohibition (`SEC-002`) | IMPLEMENTED | History rewrite required if it ever happens. **Low-Medium.** |

---

## 5. Highest residual risks (honest summary)

| Rank | Risk | Why it stays high |
| --- | --- | --- |
| 1 | **THR-040 / THR-054 — profile & cookie theft** | The persistent professional profile is a standing bearer credential. Container hardening reduces, but does not remove, host-level and escape paths. No volume encryption yet. |
| 2 | **THR-061 — semantic UI drift** | A selector can remain valid while its meaning changes. Detection is fundamentally hard; attestation campaigns are periodic, not continuous. |
| 3 | **THR-070 / THR-071 — injection and confused deputy** | The MCP client is outside our trust boundary. Our only real controls are semantic tools, classification and human approval quality. |
| 4 | **THR-053 — tenant/account confusion** | Explicit tenant pinning is not yet enforced. |
| 5 | **THR-123 — insider/maintainer change to gates** | Structurally unmitigable in a single-maintainer repository; documented, not solved. |
| 6 | **THR-090 — portal misconfiguration** | The control plane currently trusts the edge for caller authentication. |

---

## 6. Explicitly out of scope

- Host operating system compromise of the operator's machine (AC-6 with root).
- Microsoft-side compromise of Entra ID or Planner.
- Physical access to the host.
- Attacks against the operator's Microsoft Authenticator device.

These are acknowledged, not mitigated. They are excluded from residual-risk reduction claims.

---

## 7. Review cadence

**THR-900** The threat model is re-reviewed on: any new mutation class, any new external
integration, any UIContract attestation campaign, any change to ingress or network topology, and
at every minor release. See [docs/governance.md](./governance.md) `GOV-070`.
