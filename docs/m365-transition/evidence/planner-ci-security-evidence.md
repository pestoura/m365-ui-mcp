# Planner CI & Security Evidence — Pre-M365 Baseline

Baseline commit: `232c72632ab5c93d0bee70ac588af08422cbc42d`  
Baseline tag: `planner-pre-m365-0.1.0`

## P-004 delivery closure

PR #214 (`feat/p004-contract-versioning`) was created because Phase 0 discovered legitimate Planner work not yet merged to `main`.

The PR was merged only after its documentation and CI gates completed successfully. A fresh push CI run then executed on the resulting `main` merge commit.

## Post-merge evidence

- CI workflow run: `31240137868` — `SUCCESS`
- Canonical documentation workflow run: `31240137869` — `SUCCESS`

The CI run executed the applicable baseline gates:

| Gate | Result |
|---|---|
| compile | PASS |
| Ruff lint | PASS |
| mypy/type | PASS |
| canonical documentation consistency | PASS |
| contract/schema validation | PASS |
| pytest unit/integration mock-only suite | PASS |
| release contract validation | PASS |
| package wheel/sdist build | PASS |
| isolated acceptance | PASS |
| base-image digest pinning | PASS |
| dependency/filesystem HIGH/CRITICAL scan | PASS |
| secret scanning | PASS |
| repository secret invariant | PASS |
| Docker control-plane build | PASS |
| Docker browser-worker build | PASS |
| Trivy control-plane HIGH/CRITICAL | PASS |
| Trivy browser-worker HIGH/CRITICAL | PASS |
| CycloneDX control-plane SBOM | PASS |
| CycloneDX browser-worker SBOM | PASS |
| SBOM validation/upload | PASS |

The misconfiguration scan is advisory in the current workflow and completed successfully; it is not represented as a stronger blocking gate than the repository actually defines.

## Explicit non-evidence

- No live Microsoft 365/Planner tenant acceptance was executed.
- No live UIContract attestation exists.
- No live mutation test exists because the baseline has zero mutation tools.
- No gate is reported PASS merely because it is documented.

## Security baseline findings

Preserved controls:

- fail closed;
- no raw generic browser primitives exposed over MCP;
- no browser cookies/tokens/storage state exported to the control plane;
- no automatic MFA approval;
- no Conditional Access bypass;
- dedicated browser-profile abstraction;
- structured redaction/sanitized errors;
- low-cardinality metric labels;
- no live mutations in 0.1.0;
- pinned base images and blocking HIGH/CRITICAL image scans.

Transition hardening findings:

- branch protection/required checks were observed disabled;
- browser readiness does not yet prove a real Chromium lifecycle;
- browser worker live egress is blocked by current internal-only Docker topology;
- global UI attestation creates excessive blast radius;
- policy and worker protocol require metadata-driven/typed generalization.
