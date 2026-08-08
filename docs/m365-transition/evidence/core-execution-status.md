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
| CORE-006 | PASS | Generic browser/profile lifecycle boundary merged through PR #220 to `ccf91b1afa61c7181b48fa43b4acfcb87ff78f9f`. Initial PR Ruff gate rejected hard-coded temporary test paths (`S108`); tests were corrected without suppressing the rule at `89562bb5661df3f6d92ed07e5fac5078587e8cca`. PR docs `31254151199` and CI `31254151198` SUCCESS; post-merge docs `31254342686` and CI `31254342688` SUCCESS. |
| CORE-007 | PASS | Closed Application Registry merged through PR #221 to `d8d46fe9782abc104e6fd5580e7a0c0d269f8cd8`; PR docs `31254585897` and CI `31254585901` SUCCESS; post-merge docs `31254742904` and CI `31254742912` SUCCESS. `planner` is `ENABLED`; `outlook` is `RESERVED` with no registrar until Planner parity. |
| CORE-008 | IMPLEMENTED_AWAITING_GATES | Canonical Tool Registry added for all 17 current public Planner tools with schemas, governance metadata, implementation state and compatibility disposition. No FastMCP registration behavior changed. |
| CORE-009 | NOT_STARTED | Dynamic semantic MCP registration. |
| CORE-010 | NOT_STARTED | Tool profiles/projections. |

## Current composition

```text
m365_mcp.server
    -> m365_mcp.application_registry
    -> m365_mcp.control_plane
    -> planner_mcp.registration
    -> planner_mcp.tools

m365_mcp.tool_registry             # canonical governance metadata; CORE-008
```

## CORE-008 boundary decision

The Tool Registry becomes canonical metadata before it becomes the registration engine. This separation allows independent validation against the existing 17-tool public surface and avoids coupling a metadata migration to a behavioral FastMCP registration change.

Current registry invariants:

- exactly the 17 existing `planner_*` tools;
- code names = ToolManifest names = ExtendedToolManifest names = registry names;
- every tool is `PRESERVE`;
- current tools remain `READ`;
- mock-only/not-attested states are retained honestly;
- no Outlook tool is introduced;
- no generic executor or browser primitive is introduced.

## Current compatibility invariants

- Repository identity is `m365-ui-mcp`.
- Canonical Python identities are `m365_mcp` and `m365_browser_worker`.
- `M365_*` is canonical configuration; `PLANNER_*` remains a bounded alias.
- All 17 current public `planner_*` tools remain `PRESERVE` with unchanged typed signatures.
- FastMCP server name remains `planner-mcp` during this behavior-preserving extraction.
- Existing `planner_mcp_*` metric names are not renamed by CORE-008.
- State schema/path are not migrated by CORE-008.
- No Outlook capability is implemented or promoted live.
- No raw browser primitive or session-secret export is introduced.
- `CORE-025` remains mandatory before any live M365 worker egress claim.

## Next gate

```text
CORE-008 PR CI/security/images/SBOM GREEN
        -> merge
        -> post-merge main GREEN
        -> CORE-009
```
