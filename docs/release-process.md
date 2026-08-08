# Release Process

Scope: the gate sequence a change must pass to reach `main` and then a tagged release of `pestoura/planner-mcp`. Companions: [testing.md](testing.md), [acceptance.md](acceptance.md), [deployment.md](deployment.md), [governance.md](governance.md), [traceability.md](traceability.md), [definition-of-done.md](definition-of-done.md).

Two absolute rules:

1. **CI never mutates a live Planner tenant.** Every automated gate runs against the mock UI.
2. **No release note, README line, capability matrix row, or tool description may claim live Planner support without a live browser-evidenced attestation.** Mock-UI evidence proves logic, not reality.

## 1. Gate sequence

| # | Gate | Trigger | Blocking | Evidence |
|---|------|---------|----------|----------|
| G1 | Compile / import | every push | yes | build log |
| G2 | Lint / format / link check | every push | yes | lint report |
| G3 | Type check | every push | yes | type report |
| G4 | Unit + schema + contract tests | every push | yes | junit + coverage |
| G5 | Mock-UI tests + selector attestation (A/B/C) | every PR | yes | junit + attestation JSON |
| G6 | Security scanning | every PR | yes | scanner report |
| G7 | SBOM generation + diff | every PR | yes | SBOM artifact |
| G8 | Compose / digest lint | every PR touching deploy | yes | lint report |
| G9 | Isolated acceptance (A2) | nightly + pre-release | yes for release | evidence bundle |
| G10 | PR review + traceability | before merge | yes | review record |
| G11 | Post-merge verification | after merge to main | yes | main pipeline + deploy smoke |
| G12 | Live read-only attestation (A3) | before any live-support claim | yes for such claims | attestation + bundle |

A gate is either green or the change does not advance. There is no "warn" state, and a gate that did not run is reported as *unavailable with a reason* — never as passed.

## 2. G1–G3 — Compile, lint, type

| Check | Tool class | Failure policy |
|-------|-----------|----------------|
| Import graph loads without side effects | build step | fail |
| Formatting | formatter `--check` | fail; no auto-fix commits on protected branches |
| Lint | project ruleset; per-file ignores require an inline justification | fail |
| Types | strict mode; `Any` escapes require an inline justification | fail |
| Dead code / unused dependencies | analyzer | fail |
| Documentation links | relative-link checker across `docs/` | fail |

## 3. G4 — Unit, schema, contract

Runs layers L1–L3 of [testing.md](testing.md). Thresholds: 100 % pass; control-plane coverage ≥ 90 % lines / 85 % branches; worker logic ≥ 85 %; redaction suite green with **zero skips**; schema backward-compatibility check against the previous release.

Additional CI-safety assertions executed here, not optional:

| Assertion | Failure meaning |
|-----------|-----------------|
| `PLANNER_ENV=ci` enforced | A job could otherwise run in live mode |
| No Planner secret names present in the environment | Credentials leaked into CI scope |
| Navigation allowlist resolves to loopback only | A test could reach the internet |
| Static grep for live Planner/login hostnames outside `docs/` and the allowlist module | Hard-coded live target |
| Egress denied except loopback and the package proxy | Network isolation broken |

## 4. G5 — Mock UI and selector attestation

Playwright suites against the local mock Planner UI, plus selector attestation sub-layers A (registry integrity), B (mock resolution) and C (semantic assertion). Requirements: 100 % pass, retries disabled, zero flakes across three consecutive scheduled runs, and no raw selector strings outside the registry.

The pipeline summary must contain, verbatim: *"Mock-UI evidence; does not constitute live Planner verification."* This prevents the artifact from being misread later as live proof.

## 5. G6 — Security

| Check | Blocking condition |
|-------|--------------------|
| Dependency vulnerability scan | any critical, or high without an approved dated exception |
| Secret scanning (repo + diff) | any finding |
| Static analysis (security rules) | any high-confidence finding |
| Container image scan | any critical |
| Hardening assertions | any prohibited compose construct |
| Redaction detector over fixture logs | any finding |

Exceptions are recorded in the governance log with an owner and an expiry date; an expired exception fails the gate automatically.

## 6. G7 — SBOM

An SBOM is generated for each image and for the Python environment, attached as a build artifact, and diffed against the previous release. Unexpected package additions, a license change into a disallowed class, or a package without a corresponding lockfile entry block the release. The SBOM digest is recorded in the release record and in the acceptance bundle's `environment.json`.

## 7. G8 — Compose and digest lint

Enforces [deployment.md](deployment.md): every `image:` and `FROM` pinned by `@sha256:`; no `:latest`; no Docker socket, host `$HOME` or `/` mounts; no `privileged`; no `network_mode: host`; `read_only: true`, `cap_drop: [ALL]`, `no-new-privileges` and a non-root user on every service; no host publication other than the loopback admin port; `worker-net` declared `internal: true`; tmpfs entries present with size limits; secrets referenced as files.

## 8. G9 — Isolated acceptance (A2)

Full compose stack with the mock UI, per the procedure in [acceptance.md](acceptance.md). Produces an evidence bundle whose manifest maps every global acceptance criterion to `pass`, `fail`, or a justified `not_applicable`. The release blocks unless every criterion resolves.

Runs nightly on `main` and mandatorily on the release-candidate commit. A bundle is bound to a git sha; a bundle from a different sha is never accepted as evidence.

## 9. G10 — PR review

| Requirement | Detail |
|-------------|--------|
| Scope | One logical change; refactors separated from behaviour changes |
| Backlog linkage | PR references at least one existing P-key |
| Traceability | [traceability.md](traceability.md) updated when a requirement, ADR, or test mapping changes |
| ADR | Any architectural decision carries an ADR in the same PR |
| Docs | Behaviour changes update the relevant document in the same PR |
| Evidence claims | Any capability-status upgrade cites a bundle id |
| Reviewer | At least one reviewer who did not author the change |
| Checklist | The [definition-of-done.md](definition-of-done.md) Level 0 checklist is completed in the PR body |

## 10. G11 — Post-merge

On merge to `main`: full pipeline re-run on the merge commit (not merely the PR head), image build and push by digest, nightly isolated acceptance scheduled, deploy to the operator host by digest, health checks, a read-only smoke tool call through the Portal, and recording of the running digests in the deployment log. Failure at any step triggers rollback to the previous digests per [deployment.md](deployment.md).

## 11. G12 — Live read-only attestation

Required **only** when a change would upgrade a capability status to `live-read-verified` or higher, or when the release notes would describe live Planner behaviour.

| Step | Requirement |
|------|-------------|
| Precondition | G1–G11 green on the exact release-candidate sha |
| Mode | `PLANNER_MODE=read_only`; mutating handlers not registered at all |
| Operator | A named human present for the whole session |
| Output | Selector attestation with `miss == 0`, redacted logs, sanitized screenshots |
| Verification | Audit export shows zero mutating operations |
| Recording | Bundle id referenced by every capability row it upgrades |

If G12 has not been run, the release notes must state, verbatim: *"Verified against the mock Planner UI only; live Planner support is not claimed."*

## 12. Versioning and release artifacts

Semantic versioning. Major on any breaking tool-schema or audit-schema change; minor on new tools or capability upgrades; patch on fixes with no contract change.

| Artifact | Content |
|----------|---------|
| Git tag | `vX.Y.Z`, signed |
| Release notes | Changes, backlog keys, capability-matrix delta, evidence bundle ids, explicit live-support statement |
| Images | Pushed by digest; digests listed in the notes |
| SBOMs | Attached |
| Evidence bundles | A2 (mandatory), A3 (when applicable) |
| Deployment record | Digests, compose hash, deployed-at timestamp |

## 13. Rollback

| Trigger | Action |
|---------|--------|
| Post-deploy health failure | Redeploy previous digests, verify health, record |
| Read-back mismatch surge | Set `PLANNER_MODE=read_only` immediately, then roll back |
| Selector drift | Freeze mutating tools, attest, patch the registry, re-accept |
| Security finding in a shipped image | Roll back, patch, re-run G6–G9 |
| Audit chain anomaly | Stop the stack, preserve volumes, open an incident |

State volumes are backward-compatible within a minor version; a major version documents its migration and the reverse procedure.

## 14. Hotfix path

Hotfixes follow the same gates with two compressions: G9 may run a reduced scenario subset covering the affected area plus the full read-back and idempotency scenarios, and G12 is skipped only when the hotfix makes no live-support claim. Nothing else may be skipped; G6 and G8 are never waived.

## 15. Communication rules

- Never present an unverified capability as supported.
- Never mark a gate "passed" that did not run; report it as unavailable with the reason.
- A blocker in the release notes is preferable to a false claim in the documentation.
- Every claim in the notes cites an artifact id; claims without artifacts are removed during review.
- Known limitations are listed explicitly, including deferred items from [roadmap.md](roadmap.md) §12.

## 16. Backlog mapping

| Gate cluster | Backlog keys |
|--------------|--------------|
| G1–G4 pipeline | P-054, P-055, P-056 |
| G5 mock UI + attestation | P-058, P-059, P-060 |
| G6–G7 security + SBOM | P-065, P-066 |
| G8 compose lint | P-063, P-064 |
| G9 isolated acceptance | P-071, P-072 |
| G10–G11 review + post-merge | P-010, P-070 |
| G12 live read-only | P-073, P-074 |
