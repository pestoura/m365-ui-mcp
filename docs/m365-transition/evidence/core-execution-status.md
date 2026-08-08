# M365 Core Execution Status

This file is the execution overlay for the `CORE-*` definitions in `../roadmap-and-backlog.md`. It records only completed/executing gates; the roadmap remains the canonical definition of scope and order.

## Phase 1

| Key | Status | Evidence / decision |
|---|---|---|
| CORE-001 | PASS | Product identity ADR accepted in PR #215; PR gates GREEN; merged to `main` at `24da6de7a88e18e7cc6f11b0216d91d602136816`; post-merge Canonical documentation run `31241171203` SUCCESS and CI run `31241171204` SUCCESS. |
| CORE-002 | PASS | Repository renamed to `pestoura/m365-ui-mcp`; PR #216 gates GREEN; merged to `main` at `7af511c1612573d9fc3822e37fa375901c3ec162`; post-merge Canonical documentation run `31241960632` SUCCESS and CI run `31241960631` SUCCESS. Repository ID and pre-M365 tag remain unchanged. |
| CORE-003 | IMPLEMENTED_AWAITING_GATES | Canonical `m365_mcp` and `m365_browser_worker` namespace/entry-point facades added while preserving Planner namespaces and all 17 public `planner_*` tools. Canonical version source moves to `m365_mcp.version`; generic implementation extraction remains intentionally assigned to CORE-005/006. |
| CORE-004 | NOT_STARTED | `M365_*` canonical configuration with bounded `PLANNER_*` aliases. |
| CORE-005 | NOT_STARTED | Generic control-plane package boundary. |
| CORE-006 | NOT_STARTED | Generic browser-worker package boundary. |
| CORE-007 | NOT_STARTED | Application Registry. |
| CORE-008 | NOT_STARTED | Canonical Tool Registry. |
| CORE-009 | NOT_STARTED | Dynamic semantic MCP registration. |
| CORE-010 | NOT_STARTED | Tool profiles/projections. |

## CORE-003 compatibility strategy

`CORE-003` establishes canonical Python package identity without prematurely duplicating or deleting the implementation:

- `m365_mcp` is the canonical package/version/CLI surface;
- `m365_browser_worker` is the canonical worker entry surface;
- `planner_mcp` and `planner_browser_worker` remain installable compatibility packages;
- the current distribution name remains `planner-mcp` until a separately gated packaging/release identity cutover; changing the repository name alone does not silently break existing installers;
- generic control-plane and browser-worker code is extracted behind the canonical namespaces only in `CORE-005/006`;
- `PLANNER_*` configuration remains unchanged until `CORE-004`;
- the public MCP tool catalog remains exactly the 17 `planner_*` tools from the immutable compatibility baseline.

This avoids two competing implementations during the transition and provides an explicit point at which compatibility can be tested on every subsequent refactor.

## Current compatibility invariants

- Repository identity is `m365-ui-mcp`.
- All 17 current public `planner_*` tools remain `PRESERVE`.
- No Outlook capability has been implemented or promoted live.
- No raw browser primitive is introduced.
- No cookie/token/storage-state export is introduced.
- Current `PLANNER_*` configuration remains authoritative until `CORE-004` passes.
- `CORE-025` remains mandatory before any live M365 worker egress claim.

## Next gate

```text
CORE-003 PR CI/security/images/SBOM GREEN
        -> merge
        -> post-merge main GREEN
        -> CORE-004
```
