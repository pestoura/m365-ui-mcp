# Testing Strategy

This document defines the Planner MCP test architecture across control plane, browser worker,
UIContract, security and acceptance.

Companions: [`acceptance.md`](acceptance.md), [`ui-contract.md`](ui-contract.md),
[`browser-worker.md`](browser-worker.md), [`release-process.md`](release-process.md) and
[`observability.md`](observability.md).

## 1. Non-negotiable CI boundary

**CI never authenticates to or mutates a live Microsoft Planner tenant.**

All automated browser testing uses deterministic local/mock surfaces. Live Planner verification is
human-initiated and initially read-only.

CI safety controls include:

- no Planner credentials/secrets in CI scope;
- CI/live mode separation with fail-closed startup guard;
- mock/loopback navigation allow-list for browser acceptance;
- no real Planner mutation endpoint/surface reachable from automated mutation tests;
- static/config checks that prevent accidental live targets;
- evidence that mutation scenarios in CI run only against the synthetic mock Planner UI.

## 2. Test layers

| Layer | Purpose | Browser | Live Planner | CI |
| --- | --- | --- | --- | --- |
| L1 Unit | pure models/policy/state/idempotency/redaction logic | no | no | yes |
| L2 Schema | JSON/model contract validation | no | no | yes |
| L3 Contract | MCP/control-plane/worker contracts | optional stub | no | yes |
| L4 Mock UI integration | Playwright against deterministic synthetic Planner UI | yes | no | yes |
| L5 UIContract validation | registry/semantic/mock attestation; live attestation separately | yes | read-only manual for live | CI + manual |
| L6 Isolated acceptance | full local stack with mock UI | yes | no | pre-release/CI target |
| L7 Live read-only acceptance | real tenant capability/UI evidence | yes | read-only | never automated |
| L8 Live mutation acceptance | dedicated isolated test plan only, later releases | yes | controlled write | never CI |

## 3. Unit tests

L1 covers at minimum:

- manifest/model validation;
- product/schema/contract version consistency;
- policy `ALLOW` / `DENY` / `REQUIRE_APPROVAL` and fail-closed defaults;
- approval expiry/binding/replay protection;
- idempotency key/fingerprint stability and conflict handling;
- operation/saga/checkpoint state transitions;
- typed lock acquisition/expiry/order;
- auth-state legal/illegal transitions;
- normalization and snapshot hashing;
- reconciliation diff/ordering logic;
- redaction of nested/adversarial values;
- metric label allow-list/cardinality rules;
- capability-state transitions;
- UIContract fragment/version/attestation rules.

Tests use injected clocks/IDs where time/randomness matters and avoid wall-clock sleeps.

## 4. Schema and contract tests

L2/L3 prove that every public interface is closed and versioned.

Required assertions include:

- every public MCP tool has matching input/output contract and manifest metadata;
- unknown properties are rejected where the contract is closed;
- the public error taxonomy contains stable sanitized codes, never raw exceptions/DOM;
- control-plane ↔ browser-worker operation envelope is semantic and closed;
- no public worker/browser primitive such as generic click/type/navigate is exposed;
- MFA sanitized event has only its approved fields;
- capability/tool/AgentCard manifests validate;
- version incompatibility fails closed.

### 0.1.0 contract gate

For release 0.1.0, an explicit test asserts:

- exactly 17 canonical public tools are registered;
- every one is classified `READ`;
- no task/bucket/dependency/scheduling/reconciliation mutation tool is registered;
- no generic browser primitive appears in the public registry.

Internal mock-tested mutation/reconciliation framework code does not change this public contract.

## 5. Mock Planner UI

The mock UI is synthetic and deterministic. It mirrors only the structural/semantic contracts needed
for tests and contains no real tenant data.

Fixture families include:

- login/auth-required;
- MFA number matching;
- authenticated Planner landing surface;
- plan list/detail;
- task list/detail;
- bucket/dependency structures;
- session expiry;
- UI drift / selector missing / semantic mismatch;
- Conditional Access blocker;
- device enrolment/managed-device prompt;
- slow/timeout/partial-operation behavior for later mutation-framework tests.

The mock may model writes to prove mutation safety infrastructure in isolation. That does **not**
make those writes part of the 0.1.0 public MCP surface or prove live Planner support.

## 6. UIContract tests

Automated UIContract tests prove:

- every selector reference exists in the centralized registry;
- code does not contain ad-hoc raw selectors outside the approved boundary;
- preferred strategies use role/accessibility/semantic/stable attributes before structural
  selectors;
- each required fragment declares fallback strategy where applicable, semantic role, UI version,
  evidence, attestation state, last validated, expiry and confidence;
- mock selectors resolve to the intended semantic element;
- structural/semantic drift produces `UI_DRIFT` and **zero arbitrary exploratory action**;
- unattested required fragments refuse execution.

Live attestation is manual/read-only and records sanitized evidence metadata/hashes. Mock attestation
never upgrades a capability to live-supported state.

## 7. Authentication/MFA tests

Test the formal state machine:

```text
UNKNOWN
READY
AUTH_REQUIRED
MFA_REQUIRED
WAITING_FOR_MFA
AUTHENTICATED
SESSION_EXPIRED
AUTH_FAILED
```

Required negative cases:

- no password automation path;
- no password/token/cookie persistence;
- no successful auth inference from “login form absent” alone;
- MFA notification can surface the number but offers no approval path;
- Telegram/Hermes/ChatGPT cannot approve MFA;
- Conditional Access managed/compliant/enrolled/certificate requirement becomes
  `BLOCKER_CONDITIONAL_ACCESS` with no retry/bypass;
- Intune/Company Portal/Identity Broker/Entra registration/MDM/EDR/certificate prompts are refused;
- session expiry transitions cleanly and requires interactive recovery.

## 8. Read-model tests

For P-025..P-030, test:

- plan list determinism/pagination/empty state;
- plan detail not-found and ambiguity behavior;
- task normalization and partial/unknown field handling;
- bucket ordering/membership consistency;
- dependency edge type parsing for `FS`, `SS`, `SF`, `FF`;
- project snapshot consistency and deterministic `snapshot_hash`;
- degraded/unavailable capability sections are explicit, never silently omitted;
- all UI-dependent reads require the relevant UIContract evidence state.

## 9. Mutation-framework tests

P-031 may be tested against mocks before live mutation tools are released. Tests prove:

- policy is evaluated before apply;
- missing/invalid policy denies;
- approvals are exact/single-use/non-replayable;
- idempotency prevents duplicate effect;
- typed lock covers apply + read-back;
- timeout triggers read-back before any retry;
- write response alone is not success;
- read-back mismatch/partial state is surfaced;
- unverifiable result becomes `UNKNOWN_OUTCOME`;
- saga/checkpoint recovery never blindly replays verified steps;
- UI drift after planning stops the mutation rather than clicking around.

These are mock/isolated safety proofs, not live Planner mutation claims.

## 10. Isolated acceptance

L6 runs the complete local topology required by the candidate release:

```text
MCP client/test driver
  → planner-mcp
  → private browser worker
  → Playwright/Chromium
  → mock Planner UI
```

IA-01..IA-16 are the canonical end-to-end acceptance family owned by P-069. The exact scenario list
is maintained in [`acceptance.md`](acceptance.md) and implementation tests.

Evidence is bound to the exact git SHA and includes only sanitized logs/audit/metrics/results and
required environment/version/digest data.

## 11. Live read-only acceptance

L7 is manual and human-operated:

- real professional Chromium profile;
- real Planner Premium tenant;
- `read_only` mode;
- zero registered mutation tools;
- UIContract/live capability observation;
- plan/task/project reads only;
- sanitized evidence hashes/metadata;
- explicit blocker recording if Conditional Access or missing tenant capability prevents validation.

Only capabilities actually observed/tested may advance from `UNVERIFIED_LIVE` toward
`DISCOVERED`/`READ_ATTESTED`/`SUPPORTED` as the capability policy allows.

## 12. Live mutation acceptance — later releases

Never run from CI or on a production plan.

When enabled later, use a dedicated disposable/non-production Planner plan created specifically for
acceptance. Each operation is governed, approved where required, read back and evidenced. Destructive
tests stop on the first unexpected divergence.

## 13. Security/supply-chain tests

The CI target includes:

- secret scanning;
- dependency scanning;
- Trivy filesystem;
- control-plane image build + scan;
- browser-worker image build + scan;
- HIGH/CRITICAL policy enforcement;
- Docker/Compose hardening checks;
- real digest pinning checks;
- CycloneDX SBOM generation for both production images;
- SBOM schema/content validation;
- release evidence publication.

`BLOCKER_IMAGE_DIGEST_PINNING` remains unresolved until the real registry digests are recorded.

## 14. Documentation/traceability tests

`scripts/check_docs.py` is a blocking gate and must end with:

```text
errors = 0
warnings = 0
```

It checks canonical documents/ADRs, requirement references, backlog/EPIC integrity, critical-path
consistency, relative links and legacy/parallel specification contamination.

P-071/P-072 extend this into full requirement ↔ backlog ↔ test/evidence closure as implementation
lands.

## 15. Determinism and flake policy

- fixed synthetic fixtures/seeds;
- injected clock/ID generation;
- event/condition waits instead of fixed sleeps;
- explicit Playwright timeouts;
- isolated browser context/profile for tests where appropriate;
- retry disabled at test-runner level when it would hide flakes;
- flaky tests are defects with an owning backlog/issue, not silently ignored gates.

## 16. Backlog mapping

| Test concern | Canonical P-key(s) |
| --- | --- |
| Foundation packaging/contracts | P-001..P-010 |
| Browser worker/UI/mock | P-011..P-017 |
| Authentication/MFA/CA/enrolment | P-018..P-024 |
| Read model | P-025..P-030 |
| Mutation framework mock safety | P-031 |
| Reconciliation safety | P-049..P-053 |
| Security/observability/supply chain | P-061..P-067 |
| Complete CI | P-068 |
| IA-01..IA-16 isolated acceptance | P-069 |
| Live read-only protocol | P-070 |
| Traceability/docs gates | P-071, P-072 |
| Release gates/0.1.0 | P-073, P-074 |
