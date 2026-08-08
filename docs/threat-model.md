# Threat Model

Method: STRIDE per trust-zone boundary (zones defined in [architecture.md](architecture.md#5-trust-zones)),
plus product-specific abuse cases. Every mitigation maps to a requirement ID in
[traceability.md](traceability.md).

## 1. Assets

| ID | Asset | Impact if compromised |
|---|---|---|
| A1 | Authenticated professional browser session | Full impersonation in tenant |
| A2 | Professional password | Account takeover, tenant-wide |
| A3 | MFA approval channel | Bypass of second factor |
| A4 | Project data (plans, tasks, people, goals) | Confidentiality/integrity loss |
| A5 | Approval ledger | Governance bypass, replay |
| A6 | Evidence/logs | Data leak via artefacts |
| A7 | Personal device integrity/privacy | Corporate control of a personal machine |

## 2. Boundaries

- **B1** MCP client -> Cloudflare Portal
- **B2** Portal -> control plane
- **B3** Control plane -> worker
- **B4** Worker -> Chromium/Planner UI
- **B5** Control plane -> Hermes
- **B6** Human -> Authenticator

## 3. STRIDE

| # | Boundary | Threat (STRIDE) | Mitigation |
|---|---|---|---|
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

## 4. Abuse cases

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

## 5. Residual risks (accepted for A1)

| ID | Risk | Why accepted | Compensating control |
|---|---|---|---|
| R1 | UI automation is inherently brittle | Premium capability is not otherwise reachable | UIContract + fail closed + drift metrics |
| R2 | Live session on a personal host is high value | Human owns the identity by design | Isolated profile, no personal browsing, revocation runbook |
| R3 | Tenant policy may make the product unusable | Out of our control | Explicit `BLOCKED_CONDITIONAL_ACCESS` / `UNSUPPORTED_TENANT` states |
