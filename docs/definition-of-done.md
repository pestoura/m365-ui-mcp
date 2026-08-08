# Planner MCP Definition of Done

For this project, **done means implemented, validated and evidenced**. A statement in documentation,
a local assumption, an unexecuted CI job or a mock-only capability claim is not sufficient evidence
for a live-support assertion.

This document is normative with [`release-process.md`](release-process.md),
[`testing.md`](testing.md), [`acceptance.md`](acceptance.md),
[`traceability.md`](traceability.md) and [`governance.md`](governance.md).

## 1. Universal rules

A change is never done when any of these conditions holds:

- a required gate is red, skipped unexpectedly or unavailable;
- documentation validation has any error or warning;
- the public MCP surface exposes a generic browser primitive;
- a capability is promoted without evidence;
- a mutation can bypass policy, approval when required, idempotency, typed lock, read-back or
  checkpoint semantics;
- a retry can repeat a mutation blindly after an unknown outcome;
- a UIContract mismatch can lead to exploratory clicks during a mutation;
- authentication requires storing a password, access token, refresh token or exported cookies;
- a personal-device enrolment/compliance bypass is attempted;
- a production base-image digest has been guessed rather than verified from a registry;
- source, logs, metrics, evidence or reports contain prohibited secrets/session material;
- CI can mutate a live Planner tenant.

## 2. Level 0 — Atomic PR

Every implementation PR must satisfy the applicable criteria below.

| ID | Criterion | Evidence |
| --- | --- | --- |
| PR-01 | Work is on an atomic branch, not developed directly on `main`. | branch/PR metadata |
| PR-02 | PR references the canonical P-key(s) and has one coherent purpose. | PR body |
| PR-03 | Affected canonical documentation and traceability are updated in the same PR. | diff + docs gate |
| PR-04 | Architectural decisions have an ADR. | ADR diff/review |
| PR-05 | Compile, ruff and strict mypy pass. | G1 |
| PR-06 | Unit, schema and contract tests pass. | G2 |
| PR-07 | Security-sensitive behaviour has negative/fail-closed tests. | G2/G3/G4 |
| PR-08 | Browser/UI changes are exercised against the mock UI and isolated browser harness. | G3 |
| PR-09 | No selector/navigation primitive exists outside the UIContract boundary. | repo/static gate |
| PR-10 | Secret/dependency security gates pass. | G4 |
| PR-11 | Container/supply-chain gates pass when deployment artifacts change. | G5/G6 |
| PR-12 | Capability-state upgrades cite evidence of the required level. | capability/evidence review |
| PR-13 | All applicable required gates are GREEN/PASS on the exact PR head. | GitHub checks |
| PR-14 | No unresolved security/privacy blocker is hidden by a workaround. | review + blocker record |

If a required gate cannot execute because GitHub Actions, billing, quota or another external
prerequisite is unavailable, PR-13 is not met.

## 3. Level 1 — Backlog item P-001..P-074

A P-key is done only when:

1. all of its explicit acceptance criteria in [`backlog.md`](backlog.md) are met;
2. its deliverables exist in the canonical branch/main after merge;
3. its required tests and security acceptance exist and pass;
4. related requirement IDs and ADRs are traceable;
5. relevant operational/observability behaviour is documented;
6. its evidence is bound to the implementing commit/merge SHA;
7. post-merge verification of the exact `main` SHA passes;
8. the GitHub issue is closed only after the evidence above exists.

A code skeleton can close a skeleton-specific backlog acceptance criterion, but it is not evidence
that the corresponding live Planner capability is supported.

## 4. Level 2 — EPIC

An EPIC is done when:

- every included P-key is Level 1 done, or an explicitly governed deferral identifies the target
  release and does not invalidate the EPIC exit goal;
- its architecture/security/privacy requirements are implemented and traceable;
- isolated acceptance covers the user-visible and failure behaviour introduced by the EPIC;
- no unresolved HIGH/CRITICAL security finding attributable to the EPIC remains without a valid,
  dated and approved exception;
- alerts/runbooks/operational evidence exist where the EPIC introduces an operational failure mode;
- documentation has no placeholders or contradictory P-key/ADR mappings;
- the EPIC exit evidence is recorded and reviewable.

The canonical EPIC ownership is:

| EPIC | P-keys | Scope |
| --- | --- | --- |
| EPIC-01 | P-001..P-010 | Foundation |
| EPIC-02 | P-011..P-017 | Browser Worker / UI |
| EPIC-03 | P-018..P-024 | Authentication / MFA |
| EPIC-04 | P-025..P-030 | Read Model |
| EPIC-05 | P-031..P-036 | Mutations |
| EPIC-06 | P-037..P-045 | Scheduling / Project Management |
| EPIC-07 | P-046..P-053 | Reconciliation / Blueprints |
| EPIC-08 | P-054..P-060 | Reporting / Portfolio |
| EPIC-09 | P-061..P-067 | Security / Governance / Observability |
| EPIC-10 | P-068..P-074 | Acceptance / Release |

## 5. Level 3 — Release 0.1.0

`0.1.0` is done only when all applicable requirements below are met.

### Public MCP contract

- exactly 17 canonical public tools are registered;
- every registered 0.1.0 tool is classified `READ`;
- no task/bucket/dependency/scheduling/sharing/reconciliation mutation tool is exposed;
- no generic `browser_click`, `browser_type`, `browser_exec`, `navigate` or equivalent primitive is
  exposed;
- contracts/manifests/tool metadata and product/schema/contract versions validate.

### Read model and capability truthfulness

- plan/task/project reads are schema-valid and deterministic in the accepted test environment;
- a project snapshot has explicit consistency/hash semantics;
- every UI-dependent operation references a UIContract fragment;
- an unattested/drifted fragment fails closed;
- all capability states remain evidence-driven;
- any capability not validated live remains explicitly non-supported/non-attested as appropriate;
- Microsoft Graph availability is never used as a capability gate.

### Authentication/privacy boundary

- formal auth states and legal transitions are tested;
- no password is stored or passed through the system;
- no access token, refresh token or exported cookie is persisted as application data;
- MFA number matching can be detected and sanitized, but approval occurs only in Microsoft
  Authenticator;
- Conditional Access managed/compliant/enrolled/certificate requirement returns
  `BLOCKER_CONDITIONAL_ACCESS`;
- Intune/Company Portal/Identity Broker/Entra registration/MDM/EDR/certificate enrolment paths are
  not automated;
- the professional Chromium profile is isolated from personal browser/home/credential material.

### Security/governance

- policy fails closed on missing/invalid/inconsistent configuration;
- approval records, where infrastructure exists, are bound, single-use and non-replayable;
- logs are structured and redacted;
- metrics are low-cardinality and exclude task/plan/user/email/title/URL/operation identifiers as
  labels;
- container posture is non-root, capability-dropped, no-new-privileges, private for the worker and
  free of prohibited host mounts;
- secret and dependency scanning pass.

### Supply chain

- control-plane production image builds;
- browser-worker production image builds;
- required base images use **real registry-validated SHA-256 digests**;
- `BLOCKER_IMAGE_DIGEST_PINNING` is closed only with that evidence;
- Trivy filesystem/image policy passes for HIGH/CRITICAL findings according to the approved
  baseline;
- control-plane CycloneDX SBOM exists and validates with non-empty components;
- browser-worker CycloneDX SBOM exists and validates with non-empty components;
- SBOMs and scan outputs are retained as release evidence.

### Test/acceptance/release evidence

- documentation validator: `errors = 0`, `warnings = 0`;
- compile, ruff, mypy, pytest and contract/schema validation pass;
- mock UI acceptance passes;
- isolated acceptance IA-01..IA-16 passes;
- CI is demonstrably unable to mutate a live Planner tenant;
- all required PR gates are green on the exact head SHA;
- post-merge gates are green on the exact `main` merge SHA;
- P-071 traceability closure passes;
- P-072 documentation completeness passes;
- P-073 release process/gates pass;
- release notes and capability matrix contain no unsupported claim;
- if live read-only acceptance has not occurred, the release explicitly states that live Planner
  support is not yet attested.

A release cannot be declared done while a required external gate is unavailable.

## 6. Mutation-specific Definition of Done for later releases

No mutation is promoted merely because its internal framework exists in 0.1.0. When mutation tools
are introduced later, each tool additionally requires:

- explicit mutation class (`SAFE_WRITE`, `GOVERNED_WRITE` or `DESTRUCTIVE`);
- policy decision before execution;
- concrete operation ID and idempotency key;
- typed resource lock with TTL where applicable;
- before/requested/after state evidence;
- approval object when policy requires it;
- deterministic read-back after execution;
- no blind automatic retry after timeout;
- `UNKNOWN_OUTCOME` when the result cannot be verified;
- saga/checkpoint/compensation handling for multi-step work;
- live mutation acceptance only in a dedicated isolated test plan, never a production plan;
- capability promotion to `MUTATION_ATTESTED`/`SUPPORTED` only after the required evidence exists.

## 7. Reconciliation-specific Definition of Done for later releases

A governed live reconciliation/apply path additionally requires:

- stable `source_id` / `external_id` binding rules;
- current-state read and normalization;
- deterministic diff;
- ordered operation plan;
- policy/approval evaluation;
- resource locks;
- per-step checkpoints;
- read-back after each applied mutation;
- exact partial/unknown state reporting;
- compensation only where proven safe;
- resume semantics that re-read before retrying uncertain work;
- convergence verification.

The presence of P-050 infrastructure in the 0.1.0 codebase does not satisfy these live-apply
criteria by itself.

## 8. Evidence quality

Acceptable evidence is reproducible, sanitized, bound to the relevant commit/environment and linked
from the relevant PR/backlog/release record.

Never use as evidence:

- a password/token/cookie/auth header;
- a raw browser profile or session export;
- unredacted tenant/business content;
- a guessed digest;
- a screenshot/DOM dump committed merely to make a capability appear attested;
- a GitHub check that did not actually execute;
- a previous-SHA result presented as proof for a new SHA;
- a Graph endpoint presented as proof that a Planner Premium UI capability exists.

## 9. Not-done examples

| Statement | Why it is not done |
| --- | --- |
| “The workflow is red only because Actions did not start.” | Required CI is unavailable; status is blocked, not PASS. |
| “Mock Planner works, therefore live Planner is supported.” | Mock proves implementation logic, not tenant/UI capability. |
| “The write returned success.” | A mutation is not verified until read-back confirms requested state. |
| “Retrying is safe because the request timed out.” | Timeout creates unknown outcome; read-back is mandatory first. |
| “Graph has the endpoint.” | Graph availability never defines support. |
| “We will pin the Docker digest later.” | Reproducibility/supply-chain evidence is incomplete. |
| “The selector probably still works.” | UIContract evidence/attestation is mandatory; drift fails closed. |
| “The operator can approve MFA in Telegram.” | MFA approval is exclusively Microsoft Authenticator. |
| “Conditional Access can be bypassed by emulating compliance.” | Violates the personal-device boundary and is prohibited. |

## 10. Backlog ownership of completion gates

| Completion concern | P-key(s) |
| --- | --- |
| CI pipeline complete | P-068 |
| Isolated acceptance | P-069 |
| Live read-only procedure | P-070 |
| Traceability closure | P-071 |
| Documentation completeness | P-072 |
| Release process/gates | P-073 |
| `0.1.0` release | P-074 |

An issue is closed only after its evidence exists; “merge now, validate later” is not an accepted
completion path for a blocking control.
