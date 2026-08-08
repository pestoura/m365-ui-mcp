# M365 Core Execution Status

This file is the execution overlay for the `CORE-*` definitions in `../roadmap-and-backlog.md`. It records only completed/executing gates; the roadmap remains the canonical definition of scope and order.

## Phase 1

| Key | Status | Evidence / decision |
|---|---|---|
| CORE-001 | PASS | Product identity ADR accepted in PR #215; merged to `main` at `24da6de7a88e18e7cc6f11b0216d91d602136816`; post-merge docs `31241171203` and CI `31241171204` SUCCESS. |
| CORE-002 | PASS | Repository renamed to `pestoura/m365-ui-mcp`; PR #216 merged to `main` at `7af511c1612573d9fc3822e37fa375901c3ec162`; post-merge docs `31241960632` and CI `31241960631` SUCCESS. |
| CORE-003 | PASS | Canonical `m365_mcp` / `m365_browser_worker` namespaces and M365 entry points introduced with Planner compatibility preserved. PR #217 initial Install gate failed because Hatch could not parse an indirect `__version__`; fixed by `cb97921cdd357f66489cd7bd7eac766f6da96ac0`, reran GREEN, merged to `09df4d3f1db9a370256dfd696b73c1a8e732881c`; post-merge docs `31242437571` and CI `31242437576` SUCCESS. |
| CORE-004 | PASS | `M365_*` canonical configuration and bounded `PLANNER_*` aliases merged through PR #218 to `71d55d7c83f75e15808480081e214659c77dd8a1`; PR docs `31242759766` and CI `31242759775` SUCCESS; post-merge docs `31242924851` and CI `31242924852` SUCCESS. |
| CORE-005 | PASS | Application-neutral `m365_mcp.control_plane` runtime introduced with injected semantic registrar in PR #219, merged to `d7cd92c48258250248c53e2fd63828835f28c52a`; PR docs `31243188263` and CI `31243188290` SUCCESS; post-merge docs `31243362589` and CI `31243590216` SUCCESS. |
| CORE-006 | PASS | Generic browser/profile lifecycle boundary merged through PR #220 to `ccf91b1afa61c7181b48fa43b4acfcb87ff78f9f`; corrected Ruff `S108` without suppressing the rule; PR docs `31254151199` and CI `31254151198` SUCCESS; post-merge docs `31254342686` and CI `31254342688` SUCCESS. |
| CORE-007 | PASS | Closed Application Registry merged through PR #221 to `d8d46fe9782abc104e6fd5580e7a0c0d269f8cd8`; PR docs `31254585897` and CI `31254585901` SUCCESS; post-merge docs `31254742904` and CI `31254742912` SUCCESS. `planner` is `ENABLED`; `outlook` is `RESERVED`. |
| CORE-008 | PASS | Canonical Tool Registry merged through PR #222 to `1a8f182db8727dcc83550a795a01d48a49e120a2`; PR docs `31255045872` and CI `31255045876` SUCCESS; post-merge docs `31255232889` and CI `31255232909` SUCCESS. |
| CORE-009 | PASS | Metadata-driven semantic registration merged through PR #223 to `2c250af7763a325df34f53c826adea5c01e61a3d`; PR docs `31255507196` and CI `31255507194` SUCCESS; post-merge docs `31255688052` and CI `31255688039` SUCCESS. Registry/binding equality and explicit typed handlers preserve the 17-tool Planner surface without a generic executor. |
| CORE-010 | IMPLEMENTED_AWAITING_GATES | Closed exposure profiles `full`, `planner`, `outlook`, `read-only` added. Profiles only filter validated definitions and cannot weaken governance metadata. `M365_TOOL_PROFILE` is canonical; no unnecessary new Planner alias is invented. |

## Current composition

```text
M365_TOOL_PROFILE
        ↓ exposure-only filter
m365_mcp.tool_profiles
        ↓
m365_mcp.tool_registry
        ↓ exact closed semantic binding
planner_mcp.registration
        ↓
17 preserved planner_* handlers (subject to selected profile)
```

## CORE-010 boundary decision

Profiles control visibility, not authorization. All Tool Registry metadata remains authoritative and unchanged. A tool excluded from a profile is simply not registered; a tool included in a profile retains its original mutation class, risk, policy/approval requirements, idempotency and implementation state.

Current profile counts are `full=17`, `planner=17`, `read-only=17`, `outlook=0` because Outlook remains reserved and has no Tool Registry definitions yet.

## Current compatibility invariants

- Repository identity is `m365-ui-mcp`.
- Canonical Python identities are `m365_mcp` and `m365_browser_worker`.
- `M365_*` is canonical configuration; bounded historical `PLANNER_*` aliases remain only where they existed.
- All 17 current public `planner_*` tools remain `PRESERVE` with unchanged typed signatures under the default `full` profile.
- FastMCP server name remains `planner-mcp` during this behavior-preserving extraction.
- Existing `planner_mcp_*` metric names are not renamed by CORE-010.
- State schema/path are not migrated by CORE-010.
- No Outlook capability is implemented or promoted live.
- No raw browser primitive or session-secret export is introduced.
- `CORE-025` remains mandatory before any live M365 worker egress claim.

## Next gate

```text
CORE-010 PR CI/security/images/SBOM GREEN
        -> merge
        -> post-merge main GREEN
        -> Phase 1 CORE-001..010 complete
        -> inspect next canonical roadmap block
```
