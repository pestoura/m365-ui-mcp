# Phase 0 Execution Status

This file is the execution overlay for `roadmap-and-backlog.md`; the roadmap key definitions remain canonical.

| Key | Status | Evidence / outcome |
|---|---|---|
| M365-SETUP-001 | ACCEPTED | In-flight P-004 discovered, reconciled through PR #214; no hidden expected Planner merge remains. |
| M365-SETUP-002 | PASS | Final repository/version/branches/PRs/tags/workflows/package/contracts captured. |
| M365-SETUP-003 | PASS | Control plane, worker and Planner domain classified with mandatory implementation-state vocabulary. |
| M365-SETUP-004 | PASS | All 17 public tools inventoried; all `planner_*` marked PRESERVE. |
| M365-SETUP-005 | PASS | Applicable CI/security gates re-executed on final `main` and GREEN. |
| M365-SETUP-006 | ACCEPTED | Topology assessed: private worker ingress is good, live M365 egress is blocked by `internal: true`; mandatory `CORE-025`. |
| M365-SETUP-007 | PASS | `planner-pre-m365-0.1.0` verified at exact final SHA. |
| M365-SETUP-008 | READY_FOR_GATE | Blueprint branch is merged with final baseline and reconciliation evidence is recorded; completion requires PR #213 gates GREEN. |
| M365-SETUP-009 | PASS | Rename impact map recorded. |
| M365-SETUP-010 | CONDITIONAL_ACCEPTANCE | Phase 1 is authorized only when PR #213 is GREEN, merged, and resulting post-merge `main` gates pass. |

## Known Phase 1/Core obligations carried forward

- `CORE-008` Canonical Tool Registry.
- `CORE-011..020` scoped capabilities and fragmented UIContract.
- `CORE-021/022` real browser lifecycle and readiness.
- `CORE-025` controlled worker egress.
- `CORE-028/029` typed worker protocol/version negotiation.
- `CORE-031..043` metadata-driven governance/state/execution.
- `CORE-044..050` result shaping/provenance/observability/token economics.
- `PLN-MIG-*` parity before Outlook live implementation.

## Non-blocking governance finding

Branch protection / required-check enforcement was observed disabled. Gates have still been explicitly executed and evidenced. This should be hardened as part of production-readiness governance rather than misrepresented as currently enforced.
