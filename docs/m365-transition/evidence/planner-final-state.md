# Planner Final State — Phase 0 Evidence

## Authoritative baseline

- Repository: `pestoura/planner-mcp`
- Final Planner `main`: `232c72632ab5c93d0bee70ac588af08422cbc42d`
- Version: `0.1.0`
- Contract/schema/UIContract/tool catalog: `0.1.0`
- Baseline tag: `planner-pre-m365-0.1.0`
- Releases before transition baseline: none
- Public MCP surface: 17 read-only `planner_*` tools
- Live mutations: none
- Live Planner UI attestation: none (`UNVERIFIED_LIVE`)

## Entry-window reconciliation

Phase 0 discovered legitimate in-flight Planner work that was not present on `main`: `feat/p004-contract-versioning`. It was 14 commits ahead of the then-current `main`.

Resolution:

1. PR #214 was opened for P-004.
2. PR gates completed GREEN.
3. PR #214 was merged normally, without force.
4. Post-merge `main` CI and documentation workflows were re-executed and completed SUCCESS.
5. `main` at `232c7263...` became the Planner final-state baseline.
6. `planner-pre-m365-0.1.0` was created and verified against that exact commit.

No `P-075+` canonical Planner backlog key was found. Historical `P-001..P-074` remain stable. Duplicate/stale issue records exist and are treated as repository hygiene debt, not as permission to renumber or delete history.

## Remaining open PR/branch interpretation

- PR #213: active transition blueprint; intentionally retained and reconciled.
- PR #1: stale Foundation PR; superseded by canonical `main`, not an expected Planner merge.
- Old foundation/specification branches: stale/superseded.
- P-002/P-003/P-004 delivery branches: merged/superseded.

There is therefore no hidden expected Planner feature merge blocking the transition entry window.

## Material findings

1. **No live Planner feature may be claimed.** The worker remains mock-first and live Planner handlers are placeholders.
2. **UIContract is global and unattested.** Ten selector entries are all `UNVERIFIED_LIVE` with null values.
3. **Policy is name-coupled.** The current read allowlist is hardcoded rather than driven from canonical tool metadata.
4. **Worker protocol is ad-hoc HTTP.** There is no typed closed operation protocol/version negotiation yet.
5. **Readiness is incomplete.** Worker health does not prove Playwright/Chromium has been started and is usable.
6. **State identity remains Planner-centric.** It must be generalized without becoming a shadow M365 content store.
7. **Current Docker topology blocks live worker egress.** Worker ingress is private, but `browser-internal` uses `internal: true`; this becomes mandatory `CORE-025`.
8. **Branch protection was not enabled when observed.** CI evidence is valid because gates were explicitly executed, but future production governance should not rely on unenforced required checks.
9. **The security boundary is directionally sound.** No raw browser primitives, cookie/token export, automatic MFA approval or Conditional Access bypass are part of the public contract.

## Phase 0 interpretation

`M365-SETUP-001..007` are satisfied with evidence. `M365-SETUP-006` is an assessment PASS/ACCEPTED with a known mandatory CORE remediation (`CORE-025`), not a claim that live egress already works.

`M365-SETUP-008..010` complete only when the reconciled transition documentation passes CI, merges to `main`, and the resulting post-merge gates are GREEN.
