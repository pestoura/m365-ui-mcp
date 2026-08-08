# M365 Core Execution Status

This file is the execution overlay for the `CORE-*` definitions in `../roadmap-and-backlog.md`. It records only completed/executing gates; the roadmap remains the canonical definition of scope and order.

## Phase 1

| Key | Status | Evidence / decision |
|---|---|---|
| CORE-001 | PASS | Product identity ADR accepted in PR #215; merged to `main` at `24da6de7a88e18e7cc6f11b0216d91d602136816`; post-merge docs `31241171203` and CI `31241171204` SUCCESS. |
| CORE-002 | PASS | Repository renamed to `pestoura/m365-ui-mcp`; PR #216 merged to `main` at `7af511c1612573d9fc3822e37fa375901c3ec162`; post-merge docs `31241960632` and CI `31241960631` SUCCESS. |
| CORE-003 | PASS | Canonical `m365_mcp` / `m365_browser_worker` namespaces and M365 entry points introduced with Planner compatibility preserved. PR #217 initial Install gate failed because Hatch could not parse an indirect `__version__`; fixed by commit `cb97921cdd357f66489cd7bd7eac766f6da96ac0`, then PR/push gates reran GREEN. Merged to `main` at `09df4d3f1db9a370256dfd696b73c1a8e732881c`; post-merge docs `31242437571` and CI `31242437576` SUCCESS. |
| CORE-004 | IMPLEMENTED_AWAITING_GATES | `M365_*` canonical configuration, bounded `PLANNER_*` aliases, fail-closed dual-definition conflicts, cross-namespace credential rejection and canonical worker bind configuration implemented. |
| CORE-005 | NOT_STARTED | Generic control-plane package boundary. |
| CORE-006 | NOT_STARTED | Generic browser-worker package boundary. |
| CORE-007 | NOT_STARTED | Application Registry. |
| CORE-008 | NOT_STARTED | Canonical Tool Registry. |
| CORE-009 | NOT_STARTED | Dynamic semantic MCP registration. |
| CORE-010 | NOT_STARTED | Tool profiles/projections. |

## CORE-004 compatibility strategy

- `M365_*` is canonical.
- Equivalent `PLANNER_*` variables remain `DEPRECATED_ALIAS` until `2.0.0`.
- A canonical value and its legacy alias may coexist only when their literal values match.
- Divergent dual definitions return sanitized `CONFIG_INVALID`; neither value is disclosed.
- Credential-shaped names under either namespace are rejected before settings are parsed.
- Legacy-only configuration remains operational, including legacy missing-variable names for legacy startup paths.
- Canonical startup reports canonical missing-variable names.
- The existing default `/var/lib/planner-mcp/state.sqlite3` is intentionally not relocated by this config-only block.
- Worker host/port use the same canonical/legacy conflict policy.

## Current compatibility invariants

- Repository identity is `m365-ui-mcp`.
- Canonical Python identities are `m365_mcp` and `m365_browser_worker`.
- All 17 current public `planner_*` tools remain `PRESERVE`.
- No Outlook capability has been implemented or promoted live.
- No raw browser primitive is introduced.
- No cookie/token/storage-state export is introduced.
- `CORE-025` remains mandatory before any live M365 worker egress claim.

## Next gate

```text
CORE-004 PR CI/security/images/SBOM GREEN
        -> merge
        -> post-merge main GREEN
        -> CORE-005
```
