# Planner MCP — Governance

Status: specification (implementation-grade)
Canonical upstream: [docs/vision.md](./vision.md)
Related: [docs/architecture.md](./architecture.md) · [docs/security.md](./security.md) · [docs/threat-model.md](./threat-model.md) · [docs/privacy-boundary.md](./privacy-boundary.md)

Requirement IDs (`GOV-xxx`) are stable.

**GOV-000 — Governing principle:** *Nothing is declared supported, safe, verified or live without
recorded evidence.* Intent is not implementation, configuration is not proof, and a passing mock
test is not live support.

---

## 1. Capability lifecycle

**GOV-010** A *capability* is a Planner Premium function the system claims it can operate. Every
capability moves through explicit states, and its current state is evidence-derived, never
asserted.

| State | Meaning | Evidence required to enter |
| --- | --- | --- |
| `UNKNOWN` | Not investigated | none (default) |
| `INVESTIGATED` | UI surface identified, feasibility assessed | written analysis + UI observation notes |
| `CONTRACTED` | Selectors defined in the UIContract | UIContract entries present (may be `UNVERIFIED_LIVE`) |
| `MOCK_SUPPORTED` | Implemented and passing against the mock UI | green mock tests referenced by ID |
| `LIVE_ATTESTED` | UIContract entries verified against real Planner | attestation record: date, tenant kind, contract version, operator |
| `LIVE_SUPPORTED` | Exercised successfully against live Planner with read-back | recorded live evidence with provenance |
| `DEGRADED` | Previously supported, now failing or drifted | failure evidence, `UI_DRIFT` or read-back failures |
| `WITHDRAWN` | Removed from the supported set | decision record + rationale |

**GOV-011** State transitions are one step at a time and always forward-justified by evidence.
`MOCK_SUPPORTED → LIVE_SUPPORTED` without an intervening `LIVE_ATTESTED` is forbidden.

**GOV-012** Regression is automatic: a capability that fails live verification drops to `DEGRADED`
without requiring a decision. Restoring it requires new evidence.

**GOV-013** Capability state is exposed through the capability tooling and must match the recorded
evidence. A mismatch is a defect, not a documentation issue.

---

## 2. Tool lifecycle

**GOV-020** A new or changed MCP tool requires, before merge:

1. A semantic contract (name, intent, arguments, result schema) — no raw UI primitives (`ARCH-021`).
2. A declared mutation class (`SEC-020`) and idempotency class.
3. A declared reversibility and, for `GOVERNED_WRITE`/`DESTRUCTIVE`, a compensation design.
4. Policy rules covering it, with tests for `ALLOW`, `DENY` and `REQUIRE_APPROVAL` paths.
5. Redaction review of its result payload.
6. Metric label review (`SEC-052`).
7. Threat-model delta: which `THR-xxx` entries change, and the new residual risk.
8. An ADR when it introduces a new mutation class, a new external dependency, or an escape hatch.

**GOV-021** Tool states: `DRAFT` → `MOCK` → `LIVE_GATED` → `GENERAL` → `DEPRECATED` → `REMOVED`.
A tool may only reach `LIVE_GATED` when its capability is `LIVE_ATTESTED`.

**GOV-022** Deprecation requires a replacement or an explicit statement that the function is
withdrawn, plus a minimum one minor-version overlap before removal.

**GOV-023** Tool contracts are versioned. A breaking argument or result change requires a new tool
name or a major contract version — never a silent change.

---

## 3. Policy lifecycle

**GOV-030** Policy changes (rules, defaults, mutation-class assignments, the global mutation
enablement flag) are governed:

- documented rationale and the threat it addresses or accepts;
- tests proving the new decision matrix;
- a policy contract version bump;
- review by the accountable owner;
- an ADR when the change weakens a control or enables a new mutation class.

**GOV-031** Enabling mutations globally (`PLANNER_ALLOW_MUTATIONS`) is a release-gated decision,
not an operational toggle. It requires: attested UIContract, implemented approval consumption
(`SEC-030`…`SEC-033`), implemented idempotency (`SEC-041`), implemented locks (`SEC-043`),
read-back verification (`SEC-006`), and a signed-off threat-model review.

**GOV-032** Weakening a control is never implicit. Removing a check, relaxing a default, or
adding a bypass requires an ADR that names the accepted residual risk.

---

## 4. Selector attestation

**GOV-040** *Attestation* is the evidence-backed confirmation that a UIContract selector resolves
to the intended element in the real Planner Premium UI. It is a governance event, not a code
change.

**GOV-041** An attestation record contains: UIContract version, date, operator, tenant kind
(sanitized — never tenant identity), the selectors verified, the verification method, and the
observed outcome. Records are stored as evidence with provenance (`SEC-080`).

**GOV-042** Attestation campaigns are **read-only** unless the campaign explicitly and separately
authorises mutations on a disposable target.

**GOV-043** Selectors are never fabricated (`ARCH-081`). An unverified selector stays
`UNVERIFIED_LIVE` with a `null` value. Guessing a plausible selector is a defect.

**GOV-044** Attestation expires. A UIContract version's attestation is invalidated by: a Planner
UI change, a `UI_DRIFT` event, a read-back failure attributable to selectors, or the passage of
the configured attestation validity window.

**GOV-045** Attestation is per contract version. Bumping the contract version invalidates prior
attestation for the changed entries.

---

## 5. Change control

**GOV-050** Change classes and their requirements:

| Class | Examples | Requirements |
| --- | --- | --- |
| Editorial | docs wording, comments | review |
| Additive low-risk | new read tool, new metric | review + tests + metric/redaction review |
| Contract change | tool schema, UIContract, state schema | review + tests + version bump + migration plan |
| Control change | policy, approvals, redaction, hardening | review + tests + ADR + threat-model delta |
| Boundary change | ingress, network topology, new external integration, privacy boundary | review + ADR + threat-model re-review (`THR-900`) + explicit owner sign-off |
| Emergency | incident response | may bypass timing, never bypasses evidence; retrospective ADR within one release |

**GOV-051** Infrastructure and edge configuration (Cloudflare portal/tunnel) is change-controlled
in the same way as code, even when applied through a provider console.

**GOV-052** No change is merged that makes a claim the evidence does not support (`GOV-000`).

---

## 6. Versioning

**GOV-060** Semantic versioning applies independently to: the product, the state schema, the tool
contract, the UIContract, and the policy contract. Each version is recorded and exposed.

**GOV-061** State schema changes require a forward migration and a documented rollback position.
Destructive migrations require an ADR.

**GOV-062** Contract versions are surfaced in health/readiness output so drift between deployed
components is detectable (`ARCH-082`).

**GOV-063** A release records the exact base-image digests, dependency lockfile hash, SBOM
artifacts and scan results (`SEC-110`…`SEC-113`).

---

## 7. Release gates

**GOV-070** A release is blocked unless all of the following are green and recorded:

1. Lint and type checks.
2. Unit and integration tests (mock mode only — CI never touches a live tenant, `SEC-115`).
3. Release-contract test (versions, manifests, tool catalogue consistency).
4. Base-image digest pinning gate.
5. Trivy filesystem and image scans, no CRITICAL/HIGH.
6. Secret scanning, no findings.
7. SBOM generated and archived for both images.
8. Documentation consistency: no capability or support claim without evidence (`GOV-000`).
9. Threat-model review when the release contains a control or boundary change.

**GOV-071** A failing gate is not waived by a comment. Waiving requires an ADR naming the accepted
risk and an expiry date.

**GOV-072** Release artefacts are immutable; a fix is a new version, never a re-tag.

---

## 8. Ownership and accountability

**GOV-080** Every area has a named accountable owner: MCP contract, policy/security, browser
worker/UIContract, infrastructure/edge, privacy boundary, release management.

**GOV-081** In a single-maintainer configuration, four-eyes review is structurally impossible.
This is recorded as an accepted residual risk (`THR-123`) rather than pretended away. Compensating
practice: ADRs for every control change, and gates that fail closed in CI rather than relying on
reviewer vigilance.

**GOV-082** The privacy boundary owner has veto authority over any change touching device
enrolment, personal-data paths, or profile handling (`PRIV-001`).

---

## 9. Risk classification

**GOV-090 — Support claims require evidence.** A capability, tool or control is described as
"live", "supported", "verified" or "secure" only when a recorded evidence artefact backs it.
Otherwise it is described as planned, mock-only, or unverified — explicitly.

**GOV-091** Every threat carries a residual-risk statement (`THR-xxx`). Residual risk is reduced
only by implemented controls; `PLANNED` controls do not reduce residual risk.

**GOV-092** Risk levels: `LOW`, `MEDIUM`, `HIGH`, `CRITICAL`. `HIGH` requires a documented
mitigation plan with an owner. `CRITICAL` blocks release.

**GOV-093** Incomplete security controls are documented as incomplete with a backlog identifier —
never as done.

---

## 10. Rollback

**GOV-100** Every release has a defined rollback position: previous image digests, previous
contract versions, and the state-schema compatibility statement.

**GOV-101** Rollback must not corrupt state: a schema migration that cannot be rolled back must be
flagged as a one-way door before release.

**GOV-102** Operational rollback of a *capability* is immediate and does not require a code
release: policy can deny a tool, and the capability drops to `DEGRADED`.

**GOV-103** A rollback is an incident-relevant event and is recorded with cause, action and
verification.

---

## 11. Audit and evidence

**GOV-110** Evidence is the currency of this project. Every claim in the docs, every capability
state, every attestation, and every release gate is traceable to a stored artefact.

**GOV-111** Audit events are append-only and cover authorisation decisions, approvals and their
consumption, lock acquisition, saga transitions, refusals, and boundary events such as
`BLOCKER_CONDITIONAL_ACCESS`.

**GOV-112** Evidence is redacted before storage (`SEC-082`) and never contains secrets, identity
material or authenticated screenshots.

**GOV-113** Evidence retention follows the retention rules in
[docs/privacy-boundary.md](./privacy-boundary.md) `PRIV-060`.

---

## 12. Support-state transitions

**GOV-120** Support states for the product as a whole: `EXPERIMENTAL` → `LIMITED` → `SUPPORTED` →
`MAINTENANCE` → `END_OF_LIFE`.

| State | Entry condition |
| --- | --- |
| `EXPERIMENTAL` | default; mock-only, no live evidence |
| `LIMITED` | read-only live capability with attestation and recorded live evidence |
| `SUPPORTED` | mutations enabled under approval, with implemented approvals, idempotency, locks, read-back, and a reviewed threat model |
| `MAINTENANCE` | no new capabilities; security and drift fixes only |
| `END_OF_LIFE` | documented shutdown, state disposition and profile destruction |

**GOV-121** The current support state is `EXPERIMENTAL`. Read-only foundation work does not by
itself confer `LIMITED`; live attestation evidence does.

**GOV-122** Announcing a support-state upgrade without the recorded entry evidence is a governance
violation, not an optimistic estimate (`GOV-000`).

---

## 13. Governance requirement index

| ID range | Area |
| --- | --- |
| GOV-000 | Governing principle |
| GOV-010…013 | Capability lifecycle |
| GOV-020…023 | Tool lifecycle |
| GOV-030…032 | Policy lifecycle |
| GOV-040…045 | Selector attestation |
| GOV-050…052 | Change control |
| GOV-060…063 | Versioning |
| GOV-070…072 | Release gates |
| GOV-080…082 | Ownership |
| GOV-090…093 | Risk classification |
| GOV-100…103 | Rollback |
| GOV-110…113 | Audit and evidence |
| GOV-120…122 | Support-state transitions |
