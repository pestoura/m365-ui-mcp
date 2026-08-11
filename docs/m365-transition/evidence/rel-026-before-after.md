# REL-026 — delivery economics before/after comparison

Status: **ACCEPTANCE EVIDENCE / NO GATE RELAXATION**

REL-026 measures whether the JDS delivery model reduces avoidable work without weakening mandatory validation. The original baseline recorded 42.9% of effective JDS capabilities avoided on comparable integration waves while the project-local CI still executed the full heavy image/Trivy/SBOM chain.

## Post-JDS observations

| Sample | CI total | Fast | Tests | Repo security | Heavy | Builds | Trivy | SBOM | JDS avoided |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Phase 9 Wave F baseline | 393 s | 43 s | 35 s | 24 s | 308 s | 2 | 2 | 2 | 42.9% |
| Phase 10 Wave G baseline | 291 s | 38 s | 34 s | 34 s | 212 s | 2 | 2 | 2 | 42.9% |
| Hardening B integration | 330 s | 35 s | 40 s | 32 s | 236 s | 2 | 2 | 2 | 57.1% |
| Hardening B post-merge | 339 s | 41 s | 44 s | 37 s | 240 s | 2 | 2 | 2 | 64.3% |

The integration observation is CI run `31430248998`; its immutable delivery-economics artifact is `9078974701` with digest `sha256:2c58cf290eb96493b3b7d261f8c10956c52c1e49d4aca4ad9422390768ba4a24`. The post-merge observation is CI run `31431540353`; artifact `9079469176`, digest `sha256:ff08d48439b1c5a2e4defecd83122c9b654ce33e3e32b3d6f59489b5ce01dbca`.

## Interpretation

JDS change-impact selection improved from 42.9% avoided capabilities in the frozen baseline to 57.1% on the recent integration boundary and 64.3% on the post-merge run. That is an improvement of 14.2 and 21.4 percentage points respectively.

Wall-clock performance is intentionally interpreted conservatively. Against Phase 9 Wave F, the recent integration boundary was 63 seconds faster overall and 72 seconds faster in the heavy job. Against Phase 10 Wave G, it was 39 seconds slower overall and 24 seconds slower in the heavy job. The evidence therefore shows a clear improvement in JDS planning/selectivity but a mixed end-to-end duration result.

Most importantly, the mandatory integration boundary still executed exactly two image builds, two Trivy image scans and two CycloneDX SBOM generations. No quality, security, release or acceptance gate was removed or weakened to improve the metric.

## Acceptance result

REL-026 acceptance criteria are satisfied for the delivery-engineering scope:

- a completed integration wave is quantitatively reconstructable;
- expensive work is measured rather than estimated;
- the collector preserves bounded failure classification and does not reinterpret infrastructure failures as code regressions;
- evidence contains no branch name, user identity, email address or tenant content;
- the before/after comparison is explicit and falsifiable;
- the controller now has evidence to tune WIP or gate placement without permission to bypass mandatory gates.

This evidence is `NOT_APPLICABLE` to M365 live-support state and does not promote Outlook or any tenant capability.
