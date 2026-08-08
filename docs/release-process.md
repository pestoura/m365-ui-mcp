# Planner MCP Release Process

This document defines the blocking path from an atomic feature branch to `main` and from `main` to a
versioned Planner MCP release. It is normative and must be read with
[`testing.md`](testing.md), [`acceptance.md`](acceptance.md),
[`deployment.md`](deployment.md), [`traceability.md`](traceability.md) and
[`definition-of-done.md`](definition-of-done.md).

## 1. Absolute release rules

1. **Merge only on GREEN/PASS.** A required gate that fails, is cancelled, is skipped unexpectedly,
   or cannot run because an external service is unavailable is not green.
2. **CI never performs a mutation against a live Planner tenant.** Browser-level CI uses the mock
   Planner UI and isolated environments only.
3. **Release 0.1.0 exposes only the canonical 17 `READ` tools.** Internal mutation/reconciliation
   safety infrastructure may exist but no public mutation tool or tenant `apply` path is enabled.
4. **No live capability claim without live browser evidence.** Mock evidence proves logic, not the
   Microsoft Planner Premium UI in the target tenant.
5. **No invented image digest.** Base-image digest pinning is resolved only from a real registry
   digest and recorded as evidence. Until then `BLOCKER_IMAGE_DIGEST_PINNING` remains open.
6. **Security/privacy boundaries fail closed.** Conditional Access, UI drift, invalid policy,
   ambiguous identity/session or an unsafe personal-device path stop the affected operation.
7. **Post-merge verification is mandatory.** A green PR head does not replace verification of the
   exact merge commit on `main`.

## 2. Git workflow

```text
main
  ↓
feat/<atomic-block>
  ↓
implement
  ↓
local/static validation where available
  ↓
PR
  ↓
required CI/security/acceptance gates
  ↓
GREEN/PASS only
  ↓
merge
  ↓
post-merge verification on exact main SHA
  ↓
next block
```

No normal development is committed directly to `main`. Implementation continues automatically while
all applicable gates are green; only a real blocker interrupts the loop.

## 3. Required gate model

### G0 — Canonical documentation and traceability

Blocking checks:

- `scripts/check_docs.py` completes with `errors = 0` and `warnings = 0`;
- every canonical A1/A1.3 document exists;
- ADR-001..ADR-008 use the canonical names/decisions;
- no legacy/parallel ADR numbering is referenced;
- `docs/backlog.md` contains exactly P-001..P-074 and EPIC-01..EPIC-10 with zero-padded keys;
- relative documentation links resolve;
- requirement references resolve to their definitions;
- capability documentation contains no unsupported live claim.

Primary backlog ownership: P-001, P-071, P-072.

### G1 — Compile, lint and typing

Blocking checks:

- `python -m compileall -q src tests`;
- `ruff check .`;
- `mypy --strict src`;
- import/package sanity checks.

Primary backlog ownership: P-002, P-068.

### G2 — Unit, schema and contract validation

Blocking checks:

- `pytest` unit/integration suites;
- JSON Schema validation;
- MCP tool-contract validation;
- manifest completeness and version consistency;
- 0.1.0 read-only contract assertion: exactly 17 canonical tools and no registered mutation tool;
- policy/default-deny, auth-state, redaction, UIContract and idempotency invariants.

Primary backlog ownership: P-004, P-005, P-061..P-063, P-068.

### G3 — Mock UI and isolated browser validation

Blocking checks:

- browser tests execute against the deterministic local mock Planner UI;
- login/MFA/session-expiry/Conditional-Access/enrolment/UI-drift fixtures are exercised;
- no live-tenant hostname/credential is available to the CI job;
- UIContract tests prove unattested/drifted fragments fail closed;
- isolated browser acceptance completes without external Planner mutation.

Primary backlog ownership: P-014..P-017, P-018..P-024, P-069.

### G4 — Secret and dependency security

Blocking checks:

- repository/diff secret scanning;
- filesystem secret-pattern scanning where configured;
- dependency vulnerability scanning;
- security/static checks required by the repository baseline;
- no password, access token, refresh token, cookie, auth header, browser-session secret or tenant
  content is present in source, fixtures, logs or committed evidence.

Primary backlog ownership: P-063, P-065, P-068.

### G5 — Container build and hardening

Build both production images:

- control plane;
- browser worker.

Blocking posture checks include:

- non-root runtime;
- read-only root filesystem where supported by the runtime design;
- `cap_drop: ALL`;
- `no-new-privileges`;
- explicit tmpfs/state/profile volumes only;
- no Docker socket;
- no host home or personal credential mounts;
- browser-worker network private/internal and no published worker port;
- control-plane exposure constrained to the documented ingress model;
- every required base image pinned by a **real** `@sha256:` digest.

Primary backlog ownership: P-064, P-065.

### G6 — Trivy and supply-chain evidence

Blocking checks:

- Trivy filesystem scan;
- Trivy scan of the control-plane image;
- Trivy scan of the browser-worker image;
- HIGH and CRITICAL findings fail unless an explicitly approved, dated baseline/exception applies;
- `ignore-unfixed` may be used only according to the approved repository baseline, never to hide a
  fixed exploitable issue;
- CycloneDX SBOM generated for control plane;
- CycloneDX SBOM generated for browser worker;
- SBOM validation confirms valid format and non-empty component sets;
- SBOMs are retained as release evidence.

Primary backlog ownership: P-065, P-068.

### G7 — Isolated acceptance

Run IA-01..IA-16 against the isolated/mock stack defined by
[`acceptance.md`](acceptance.md). The suite must prove normal and fail-closed paths, including at
least UI drift, Conditional Access, enrolment refusal, MFA detection, policy denial, approval
replay protection, timeout/read-back behaviour, container posture and telemetry hygiene.

No live Planner mutation is allowed. The evidence bundle is bound to the exact git SHA.

Primary backlog ownership: P-069.

### G8 — PR review and merge gate

Before merge:

- the PR references the relevant P-key(s);
- scope is atomic;
- affected documentation and traceability are updated;
- architectural changes include an ADR;
- no security control is weakened silently;
- capability status upgrades cite valid evidence;
- all required G0..G7 gates are GREEN/PASS on the exact PR head;
- known unavailable/non-applicable gates are explicitly distinguished; a required unavailable gate
  blocks merge.

Primary backlog ownership: P-071..P-073.

### G9 — Post-merge verification

After merge to `main`:

- rerun all applicable required checks on the exact merge SHA;
- verify `main` points to the intended merge commit;
- verify package/contracts/tool catalogue again;
- rebuild/re-scan images as required by the workflow;
- retain exact-SHA evidence;
- for deployment candidates, perform health/readiness and read-only smoke validation through the
  supported ingress path.

Failure means the block is not closed. Correct or revert; do not continue as though the merge were
healthy.

Primary backlog ownership: P-068, P-073.

### G10 — Live read-only acceptance

Required before any release note or capability matrix row claims real Planner Premium read support.

Conditions:

- operator-controlled session;
- read-only mode;
- no registered mutation tool;
- UIContract observation/attestation against the target tenant;
- sanitized evidence only;
- zero mutation audit evidence;
- missing/unsupported tenant capability remains `UNVERIFIED_LIVE`, `DISCOVERED`, `DEGRADED`,
  `UI_DRIFT` or `BLOCKED_CONDITIONAL_ACCESS` as evidence dictates; never promoted by assumption.

Primary backlog ownership: P-070, P-074.

Live mutation acceptance is not part of 0.1.0. When introduced later it runs only in an isolated test
plan specifically created for destructive/safe-write validation, never in production plans.

## 4. CI target inventory

The target GitHub Actions pipeline contains, at minimum:

- compile;
- ruff;
- mypy;
- pytest;
- contract validation;
- docs validation;
- mock UI acceptance;
- isolated acceptance;
- container build — control plane;
- container build — browser worker;
- secret scanning;
- dependency scanning;
- Trivy filesystem;
- Trivy images;
- SBOM control plane;
- SBOM browser worker;
- SBOM validation;
- release evidence publication.

A missing target gate is backlog work, not evidence that the requirement passed.

## 5. Branch protection target

`main` should require PR-based changes and the repository's blocking CI checks once those checks are
stable and runnable. Protection must not be configured to create an impossible merge deadlock while
required checks do not yet exist, but the release process itself still forbids merging a block whose
required gates are not green.

When GitHub Actions is unavailable because of billing, account, platform or quota state, the correct
status is `BLOCKED_EXTERNAL_CI`. The solution is restoration of the external prerequisite — never a
manual reinterpretation of red/skipped checks as PASS.

## 6. 0.1.0 release gate

P-074 may close and tag `v0.1.0` only when:

- G0..G9 are green on the release candidate and merge SHA as applicable;
- the public registry contains exactly the canonical 17 read-only tools;
- all capability states are truthful and evidence-backed;
- any live read claim has G10 evidence; otherwise the release explicitly states that live Planner
  support has not yet been attested;
- `BLOCKER_IMAGE_DIGEST_PINNING` is resolved with real registry digests for required production
  images;
- both image SBOMs are valid CycloneDX and retained;
- HIGH/CRITICAL Trivy policy is satisfied;
- known blockers/limitations are documented;
- rollback/runbook information is present for any deployed candidate.

## 7. Versioning

- product version, schema version, contract version, capability-manifest version and UIContract
  version are independently explicit;
- `0.1.0` establishes the initial read-only product contract;
- backward-incompatible MCP/schema changes require the appropriate semantic-version change;
- capability attestation changes do not silently change contract semantics;
- a UIContract change is versioned and re-attested for affected fragments.

## 8. Release artifacts

A production-candidate release record includes as applicable:

- git tag and exact commit SHA;
- PR/merge references and P-keys;
- gate results;
- container image digests;
- control-plane CycloneDX SBOM;
- browser-worker CycloneDX SBOM;
- vulnerability/security scan summaries;
- isolated acceptance evidence;
- live read-only evidence or an explicit statement that live support is not claimed;
- capability matrix state/delta;
- known blockers and accepted limitations;
- deployment/rollback evidence when deployed.

Evidence must not contain credentials, tokens, cookies, raw browser profile material or unnecessary
tenant/business content.

## 9. Failure and rollback

| Failure | Required response |
| --- | --- |
| CI/security gate fails | diagnose, correct and rerun; no merge |
| Required gate cannot run | mark blocked/unavailable; no merge/release |
| UIContract mismatch | `UI_DRIFT`, freeze affected capability, re-attest |
| Conditional Access requires managed/compliant device | `BLOCKER_CONDITIONAL_ACCESS`; no bypass |
| Unknown mutation outcome in later releases | read-back; if unverifiable, `UNKNOWN_OUTCOME`, no blind retry |
| Post-merge verification fails | correct or revert exact merge; block next dependent step |
| Vulnerable shipped image | roll back/pin corrected image, rebuild, rescan, regenerate SBOM/evidence |
| Audit/evidence integrity failure | stop affected release/deployment and preserve evidence for investigation |

## 10. Backlog ownership

| Release concern | Canonical P-key(s) |
| --- | --- |
| CI pipeline complete | P-068 |
| Isolated acceptance IA-01..IA-16 | P-069 |
| Live read-only acceptance procedure | P-070 |
| Traceability matrix closure | P-071 |
| Documentation completeness gate | P-072 |
| Release process and gates | P-073 |
| 0.1.0 release | P-074 |
| Container hardening | P-064 |
| SBOM/vulnerability/digest gates | P-065 |

This mapping must remain consistent with [`backlog.md`](backlog.md).
