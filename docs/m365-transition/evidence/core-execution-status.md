# M365 Core Execution Status

This file is the execution overlay for the `CORE-*` definitions in `../roadmap-and-backlog.md`. It records only completed/executing gates; the roadmap remains the canonical definition of scope and order.

## Phase 1

| Key | Status | Evidence / decision |
|---|---|---|
| CORE-001 | PASS | Product identity ADR accepted in PR #215; merged to `main` at `24da6de7a88e18e7cc6f11b0216d91d602136816`; post-merge docs `31241171203` and CI `31241171204` SUCCESS. |
| CORE-002 | PASS | Repository renamed to `pestoura/m365-ui-mcp`; PR #216 merged to `main` at `7af511c1612573d9fc3822e37fa375901c3ec162`; post-merge docs `31241960632` and CI `31241960631` SUCCESS. |
| CORE-003 | PASS | Canonical `m365_mcp` / `m365_browser_worker` namespaces and M365 entry points introduced with Planner compatibility preserved. PR #217 initial Install gate failed because Hatch could not parse an indirect `__version__`; fixed by `cb97921cdd357f66489cd7bd7eac766f6da96ac0`, reran GREEN, merged to `09df4d3f1db9a370256dfd696b73c1a8e732881c`; post-merge docs `31242437571` and CI `31242437576` SUCCESS. |
| CORE-004 | PASS | `M365_*` canonical configuration and bounded `PLANNER_*` aliases merged through PR #218 to `71d55d7c83f75e15808480081e214659c77dd8a1`; PR docs `31242759766` and CI `31242759775` SUCCESS; post-merge docs `31242924851` and CI `31242924852` SUCCESS. |
| CORE-005 | PASS | Application-neutral `m365_mcp.control_plane` runtime introduced with injected semantic registrar in PR #219, merged to `d7cd92c48258250248c53e2fd63828835f28c52a`; PR docs `31243188263` and CI `31243188290` SUCCESS; post-merge docs `31243362589` and CI `31243590216` SUCCESS. Generic runtime has no Planner imports; current projection remains exactly 17 Planner tools. |
| CORE-006 | PASS | Generic browser/profile lifecycle boundary merged through PR #220 to `ccf91b1afa61c7181b48fa43b4acfcb87ff78f9f`. Initial PR Ruff gate rejected hard-coded temporary test paths (`S108`); tests were corrected without suppressing the rule at `89562bb5661df3f6d92ed07e5fac5078587e8cca`. Current PR docs `31254151199` and CI `31254151198` SUCCESS; post-merge docs `31254342686` and CI `31254342688` SUCCESS. |
| CORE-007 | IMPLEMENTED_AWAITING_GATES | Closed validated Application Registry introduced. `planner` is `ENABLED`; `outlook` is registered as `RESERVED` with no registrar until Planner parity and the ordered Outlook phase. No plugin self-registration. |
| CORE-008 | NOT_STARTED | Canonical Tool Registry. |
| CORE-009 | NOT_STARTED | Dynamic semantic MCP registration. |
| CORE-010 | NOT_STARTED | Tool profiles/projections. |

## Current composition

```text
m365_mcp.server
    -> m365_mcp.application_registry  # explicit/closed application identities
    -> m365_mcp.control_plane         # generic FastMCP runtime
    -> planner_mcp.registration       # enabled Planner semantic registrar
    -> planner_mcp.tools              # preserved Planner behavior
```

`outlook` is present as a stable application identity but has no registrar and cannot project tools or execute UI work in CORE-007.

## CORE-007 boundary decision

Application registration is explicit, immutable after construction and fail-closed:

- duplicate application keys are rejected;
- `ENABLED` requires a semantic registrar;
- `RESERVED` forbids a registrar;
- no entry-point/plugin/filesystem discovery is used;
- registration order is deterministic;
- Outlook cannot become executable accidentally before the parity gate.

This preserves the stronger sequencing requirement over an overly literal reading of "enabled planner/outlook" in the original roadmap: both identities are registered, but only phase-authorized adapters may be executable.

## Current compatibility invariants

- Repository identity is `m365-ui-mcp`.
- Canonical Python identities are `m365_mcp` and `m365_browser_worker`.
- `M365_*` is canonical configuration; `PLANNER_*` remains a bounded alias.
- All 17 current public `planner_*` tools remain `PRESERVE` with unchanged typed signatures.
- FastMCP server name remains `planner-mcp` during this behavior-preserving extraction.
- Existing `planner_mcp_*` metric names are not renamed by CORE-007.
- State schema/path are not migrated by CORE-007.
- No Outlook capability is implemented or promoted live.
- No raw browser primitive or session-secret export is introduced.
- `CORE-025` remains mandatory before any live M365 worker egress claim.

## Next gate

```text
CORE-007 PR CI/security/images/SBOM GREEN
        -> merge
        -> post-merge main GREEN
        -> CORE-008
```
