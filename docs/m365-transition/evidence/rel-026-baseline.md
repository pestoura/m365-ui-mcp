# REL-026 — delivery economics baseline

Status: **BASELINE CAPTURED / NO GATE CONSOLIDATION YET**

This evidence establishes the pre-consolidation delivery baseline. It does not authorize removal or weakening of any M365 gate.

## Quantitative samples

| Sample | CI total | Fast | Tests | Repo security | Heavy | JDS avoided capabilities |
|---|---:|---:|---:|---:|---:|---:|
| Phase 9 Wave F integration boundary | 393 s | 43 s | 35 s | 24 s | 308 s | 42.9% |
| Phase 9 Wave F post-merge main | 315 s | 35 s | 39 s | 22 s | not separately frozen | n/a |
| Execution-index post-merge main | 290 s | not separately frozen | not separately frozen | not separately frozen | dominant | 42.9% |

The Phase 9 integration boundary executed two image builds, two Trivy image scans and two CycloneDX SBOM generations. The matching JDS plan selected 8 of 14 effective capabilities and skipped 6. In particular `container.build`, `security.container-scan` and `security.sbom` were skipped as `change-impact-not-triggered`, while the project-local integration boundary deliberately still executed them.

The execution-index main push produced the same JDS avoidance ratio: 8 of 14 effective capabilities selected and all three heavy container/SBOM capabilities skipped, while the legacy main CI still executed the complete heavy chain.

## Interpretation

The evidence demonstrates a material placement/duplication opportunity, not permission to delete validation. The heavy boundary is currently the dominant latency component on changes for which the central planner can positively determine that container/SBOM impact is absent.

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
```
