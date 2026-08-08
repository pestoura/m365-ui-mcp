# M365 Core Execution Status

This file is the execution overlay for the `CORE-*` definitions in `../roadmap-and-backlog.md`. It records only completed/executing gates; the roadmap remains the canonical definition of scope and order.

## Phase 1

| Key | Status | Evidence / decision |
|---|---|---|
| CORE-001 | PASS | Product identity ADR accepted in PR #215; PR gates GREEN; merged to `main` at `24da6de7a88e18e7cc6f11b0216d91d602136816`; post-merge Canonical documentation run `31241171203` SUCCESS and CI run `31241171204` SUCCESS. |
| CORE-002 | EXECUTED_READ_BACK_OK | Repository renamed from `pestoura/planner-mcp` to `pestoura/m365-ui-mcp`. Repository ID `1327254732`, `main` SHA and baseline tag preserved. Bridge timeout was reconciled by read-back and not retried blindly. Completion awaits this branch PR and post-merge GREEN gates. |
| CORE-003 | NOT_STARTED | Starts only after CORE-002 PR/post-merge gates are GREEN. |
| CORE-004 | NOT_STARTED | `M365_*` canonical configuration with bounded `PLANNER_*` aliases. |
| CORE-005 | NOT_STARTED | Generic control-plane boundary. |
| CORE-006 | NOT_STARTED | Generic browser-worker boundary. |
| CORE-007 | NOT_STARTED | Application Registry. |
| CORE-008 | NOT_STARTED | Canonical Tool Registry. |
| CORE-009 | NOT_STARTED | Dynamic semantic MCP registration. |
| CORE-010 | NOT_STARTED | Tool profiles/projections. |

## Current compatibility invariants

- Repository identity is `m365-ui-mcp`; runtime distribution remains 0.1.0 Planner compatibility until explicitly migrated.
- All 17 current public `planner_*` tools remain `PRESERVE`.
- No Outlook capability has been implemented or promoted live.
- No raw browser primitive is introduced.
- No cookie/token/storage-state export is introduced.
- Current `PLANNER_*` configuration remains authoritative until `CORE-004` passes.
- Current package/CLI names remain authoritative until their explicit migration gates pass.
- `CORE-025` remains mandatory before any live M365 worker egress claim.

## Next gate

```text
CORE-002 evidence/docs PR
        -> PR CI/security/images/SBOM GREEN
        -> merge
        -> post-merge main GREEN
        -> CORE-003
```
