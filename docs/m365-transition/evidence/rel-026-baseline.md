# REL-026 — delivery economics baseline

Status: **BASELINE CAPTURED / NO GATE CONSOLIDATION YET**

This evidence establishes the pre-consolidation delivery baseline. It does not authorize removal or weakening of any M365 gate.

## Quantitative samples

| Sample | CI total | Fast | Tests | Repo security | Heavy | JDS avoided capabilities |
|---|---:|---:|---:|---:|---:|---:|
| Phase 9 Wave F integration boundary | 393 s | 43 s | 35 s | 24 s | 308 s | 42.9% |
| Phase 9 Wave F post-merge main | 315 s | 35 s | 39 s | 22 s | not separately frozen | n/a |
| Execution-index post-merge main | 290 s | not separately frozen | not separately frozen | not separately frozen | dominant | 42.9% |
| Phase 10 Wave G integration boundary | 291 s | 38 s | 34 s | 34 s | 212 s | 42.9% |

The Phase 9 integration boundary executed two image builds, two Trivy image scans and two CycloneDX SBOM generations. The matching JDS plan selected 8 of 14 effective capabilities and skipped 6. In particular `container.build`, `security.container-scan` and `security.sbom` were skipped as `change-impact-not-triggered`, while the project-local integration boundary deliberately still executed them.

The execution-index main push produced the same JDS avoidance ratio: 8 of 14 effective capabilities selected and all three heavy container/SBOM capabilities skipped, while the legacy main CI still executed the complete heavy chain.

The Phase 10 Wave G boundary provides a third independent product sample. Its CI run completed in 291 seconds: fast quality 38 seconds, tests/isolated acceptance 34 seconds, repository security 34 seconds and the heavy image/Trivy/SBOM job 212 seconds. The boundary executed two image builds, two Trivy image scans and two CycloneDX SBOM generations successfully. The matching JDS plan is non-ambiguous (`ambiguousImpact=false`), detected the 11 changed Outlook automation source/test files, selected 8 of 14 effective capabilities and skipped 6 (42.9%). The skipped set again includes `container.build`, `security.container-scan` and `security.sbom` as `change-impact-not-triggered`.

The Wave G post-merge `main` run `31312397711` remains a pending observation at this capture point. Quality, tests/isolated acceptance, repository security, both image builds and both Trivy image scans are GREEN; the heavy job is still active in the CycloneDX SBOM phase. It is therefore not counted as either a post-merge regression or a completed success until GitHub gives it a terminal conclusion.

## Interpretation

The evidence demonstrates a material placement/duplication opportunity, not permission to delete validation. On the two completed product integration boundaries above, the heavy job consumed 308 seconds and 212 seconds respectively, while the JDS planner independently classified the three container/SBOM capabilities as not triggered by change impact.

The safe next step is to collect this evidence automatically for subsequent CI runs, classify failures, and compare equivalent boundaries before any gate-placement change. Any future consolidation must preserve or improve detection coverage and retain an explicit heavy boundary wherever the effective plan selects container/SBOM capabilities or another fail-safe rule requires them.

## Privacy and cardinality

The automated collector emits only low-cardinality run kinds, conclusions, durations, counts, failure classes and JDS plan counts. It does not emit branch names, user names, email addresses, tenant identities, message content or selectors.

## Source run IDs

```text
31307838926  Phase 9 Wave F integration CI
31307838928  matching Wave F JDS Audit
31308117109  Phase 9 post-merge main CI
31308567008  execution-index post-merge main CI
31308567009  matching controller JDS Audit
31312156758  Phase 10 Wave G integration CI
31312156744  matching Wave G JDS Audit
31312397711  Phase 10 Wave G post-merge main CI (pending at capture)
31312397658  matching Wave G post-merge JDS Audit
artifact 9037677741  Wave G jds-effective-plan
sha256:1b0947240cd815d7ff348dec9856c8c0aed51fd234a94cb188f8d390514263ae
```
