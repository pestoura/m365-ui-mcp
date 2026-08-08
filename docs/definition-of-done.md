# Definition of Done

Scope: the completion criteria applied at four levels — task, backlog item, epic, release — for `pestoura/planner-mcp`. Companions: [release-process.md](release-process.md), [testing.md](testing.md), [acceptance.md](acceptance.md), [traceability.md](traceability.md), [governance.md](governance.md).

Guiding rule: *done* means evidenced. A statement in a document, a passing local run, or a reviewer's confidence is not evidence. The artifacts named below are.

## 1. Level 0 — Task (a single PR)

| # | Criterion | Verified by |
|---|-----------|-------------|
| T-01 | The change references at least one existing backlog P-key. | PR template + CI check |
| T-02 | Scope is one logical change; refactors are separated from behaviour changes. | review |
| T-03 | Compile, lint, format and type gates pass (G1–G3). | CI |
| T-04 | New behaviour has tests at the lowest layer that can prove it. | review + coverage delta |
| T-05 | Unit, schema and contract suites pass (G4). | CI |
| T-06 | Coverage thresholds are met and not lowered. | CI |
| T-07 | Any new tool has a schema, a catalogue entry, an error taxonomy mapping and a policy rule. | L2/L3 tests |
| T-08 | Any new selector is registered with a primary strategy, ≥1 fallback, an owner and a semantic assertion. | L5 A–C |
| T-09 | Any new log field passes the redaction detector; no raw identifiers, content, or selectors. | L1 |
| T-10 | Any new metric uses only enumerated labels and stays inside the cardinality budget. | startup guard + L1 |
| T-11 | No prohibited deployment construct is introduced (socket, host mounts, privileged, tag-only image). | G8 |
| T-12 | Documentation affected by the change is updated in the same PR. | review |
| T-13 | An ADR accompanies any architectural decision. | review |
| T-14 | [traceability.md](traceability.md) is updated when requirements, ADRs, or test mappings change. | review + CI check |
| T-15 | No live-support claim is added without an A3 bundle reference. | CI matrix gate |
| T-16 | The PR body completes this checklist explicitly. | review |
| T-17 | At least one reviewer other than the author approves. | branch protection |
| T-18 | No new flaky test; if a test is quarantined, an owning issue exists. | CI flake report |

A PR failing any row is not merged. There is no "merge and follow up" path for T-03..T-11 or T-15.

## 2. Level 1 — Backlog item (a P-key)

| # | Criterion | Verified by |
|---|-----------|-------------|
| B-01 | All Level 0 criteria hold for every PR that implements it. | CI history |
| B-02 | The item's acceptance criteria, as written in the backlog, are each mapped to a test or an evidence artifact. | traceability row |
| B-03 | The behaviour is exercised end to end at least once in the isolated acceptance suite, or a written justification explains why it is not observable there. | bundle A2 |
| B-04 | Failure paths are tested, not only the happy path. | test review |
| B-05 | Observability exists: the behaviour is visible in logs, metrics, and — for mutations — the audit trail. | L6 evidence |
| B-06 | Operational impact is documented: configuration variables, alerts, runbook steps. | docs |
| B-07 | Security implications are reviewed against [threat-model.md](threat-model.md); new risks are mitigated or explicitly accepted with an owner. | governance log |
| B-08 | The item is closed only after the merge commit's pipeline is green on `main`. | CI |

## 3. Level 2 — Epic (EPIC-01..EPIC-10)

| # | Criterion | Verified by |
|---|-----------|-------------|
| E-01 | Every P-key in the epic is Level 1 done, or explicitly deferred with a governance note naming the target phase. | backlog |
| E-02 | The epic's exit gates in [roadmap.md](roadmap.md) are demonstrated, not asserted. | evidence artifacts |
| E-03 | All requirements mapped to the epic in [traceability.md](traceability.md) §7 have at least one closing evidence artifact. | traceability |
| E-04 | The isolated acceptance suite includes scenarios covering the epic's user-visible behaviour. | bundle A2 |
| E-05 | Documentation for the epic's area is complete, cross-linked, and free of placeholders. | link checker + review |
| E-06 | No open critical or high security finding attributable to the epic. | G6 report |
| E-07 | Alerts and runbooks exist for the epic's new failure modes. | [observability.md](observability.md) §7 |
| E-08 | A governance review records the epic as complete, with the evidence references cited. | governance log |

## 4. Level 3 — Release

| # | Criterion | Verified by |
|---|-----------|-------------|
| R-01 | Gates G1–G11 are green on the exact release candidate sha. | CI |
| R-02 | An isolated acceptance bundle (A2) exists for that sha with every criterion `pass` or justified `not_applicable`. | bundle |
| R-03 | The audit hash chain verifies over the acceptance run. | verifier output |
| R-04 | The redaction detector reports zero findings across the run's full log stream. | bundle |
| R-05 | Selector attestation reports zero misses at the level being claimed. | attest |
| R-06 | All images are digest-pinned; digests are recorded in the release notes and in `environment.json`. | G8 + notes |
| R-07 | SBOMs are attached and the diff contains no unexplained additions. | G7 |
| R-08 | The capability matrix is regenerated from evidence, never hand-edited. | CI matrix gate |
| R-09 | Any live-support claim is backed by an A3 (or A4) bundle; otherwise the notes carry the verbatim mock-only statement. | review |
| R-10 | The rollback path is documented and the previous digests are known-good. | deployment log |
| R-11 | Post-deploy health checks and a read-only smoke tool call through the Portal succeed. | deployment log |
| R-12 | The release record links every evidence artifact by id and hash. | release notes |

## 5. Definition of *not* done

These are the failure patterns this project explicitly refuses to call done.

| Pattern | Why it is not done |
|---------|--------------------|
| "It works locally." | No reproducible evidence bound to a sha. |
| "Mock UI tests pass, so live works." | Mock proves logic, not the real DOM. Requires L5-D/A3. |
| "Graph confirms the change." | Graph is contextual; only UI read-back verifies. |
| "The write returned success." | Success without read-back is unverified. |
| "Tests are skipped for now." | A skipped redaction or attestation test is a failed gate. |
| "The secret is only in CI." | Live Planner credentials must not exist in CI at all. |
| "We'll pin the digest later." | Non-reproducible builds invalidate every prior evidence artifact. |
| "Docs will follow the code." | Behaviour and documentation ship together. |
| "The operator will remember." | Runbooks and alerts, or it is not operable. |
| "It's a small change to the compose file." | Deployment constructs are security boundaries; G8 always applies. |

## 6. Evidence checklist per change type

| Change type | Minimum evidence |
|-------------|------------------|
| New MCP tool | schema, catalogue entry, policy rule, L2+L3 tests, L4 scenario, A2 scenario, docs |
| New selector | registry entry with fallback and owner, L5 A–C, mock coverage, drift-report ownership |
| New mutation path | read-back definition with guard fields, idempotency key derivation, L4 + A2 scenarios, audit row shape |
| Redaction change | detector cases (positive and negative), full-log scan in A2 |
| Metric change | label enumeration, cardinality budget update, dashboard/alert review |
| Deployment change | G8 lint, digest pin, tmpfs/volume declaration, A2 isolation assertions |
| Dependency bump | SBOM diff, scanner report, A2 re-run |
| Playwright/Chromium bump | attestation re-run (mock, and live if live support is claimed), A2 re-run |
| Documentation-only | link check, no capability status upgrade without a bundle reference |

## 7. Roles and sign-off

| Role | Signs off on |
|------|--------------|
| Author | Level 0 checklist completeness |
| Reviewer | Level 0 correctness, scope, traceability |
| Maintainer | Level 1 and Level 2 closure |
| Operator | Level 3 deployment, rollback readiness, A3 sessions |
| Governance | Epic completion, exceptions, deferrals, privacy-boundary changes |

Any exception to a criterion requires: a written justification, a named owner, an expiry date, and a governance-log entry. An expired exception fails the next gate automatically — exceptions decay, they do not accumulate.

## 8. Backlog mapping

| Level | Backlog keys |
|-------|--------------|
| Level 0 tooling (PR template, CI checks) | P-010, P-054 |
| Level 1 traceability automation | P-010, P-072 |
| Level 2 epic exit evidence | P-070, P-071 |
| Level 3 release governance | P-072, P-073, P-074 |

## 9. Worked examples

### 9.1 Adding a "set task priority" tool

| Step | Artifact |
|------|----------|
| Catalogue entry + schema | `tool-catalog.md` row, JSON schema with `additionalProperties: false` |
| Policy | Role requirement `operator`, `dry_run` supported |
| Selectors | `task.detail.priority` registered with fallback and owner, attested A–C |
| Read-back | `priority` in changed fields; `due_date`, `bucket`, `assignments` as guard fields |
| Idempotency | Key derived from plan/task id hash + intended priority |
| Tests | L1 normalization, L2 schema, L3 replay/conflict, L4 mock scenario, L6 A2 scenario |
| Observability | Counter labels reuse existing enumerations; audit row records field hashes |
| Docs | Capability matrix row created as `mock-verified` |
| Live claim | Blocked until an A3 attestation covers the priority control |

### 9.2 Bumping Chromium

| Step | Artifact |
|------|----------|
| Pin update | Playwright version + base image digest bumped together |
| SBOM | Regenerated and diffed (G7) |
| Attestation | Mock attestation re-run; live attestation required if live support is currently claimed |
| Acceptance | Full A2 re-run on the new digest |
| Release note | New digests listed; capability statuses unchanged unless re-attested |

## 10. Anti-regression rules

| Rule | Enforcement |
|------|-------------|
| Coverage thresholds may only rise | CI compares against the stored baseline |
| A criterion may not be downgraded to `not_applicable` without a written justification | review at G10 |
| A capability status may never be raised by hand | CI matrix gate |
| A quarantined test must be fixed or deleted with justification within 14 days | flake report |
| An expired security exception blocks the next gate | G6 |
| A doc claim without an artifact id is removed | review |

## 11. Quick reference card

Before requesting review, confirm: backlog key referenced; tests at the lowest useful layer; redaction unaffected or extended; metric labels enumerated; no prohibited deployment construct; docs updated; traceability updated; no live claim without an A3 bundle; checklist completed in the PR body.
