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
| CORE-006 | IMPLEMENTED_AWAITING_GATES | `m365_browser_worker.browser` now owns BrowserConfig/PersistentBrowser and Conditional Access detection; Planner browser lifecycle imports are compatibility shims. Browser profile/headless settings use canonical `M365_*` plus bounded `PLANNER_*` aliases with divergent definitions rejected fail-closed. No lifecycle semantics are promoted beyond the pre-existing implementation. |
| CORE-007 | NOT_STARTED | Application Registry. |
| CORE-008 | NOT_STARTED | Canonical Tool Registry. |
| CORE-009 | NOT_STARTED | Dynamic semantic MCP registration. |
| CORE-010 | NOT_STARTED | Tool profiles/projections. |

## CORE-005 boundary decision

The generic control plane owns only application-neutral MCP construction. Domain registration is injected through a closed typed registrar hook.

Current composition deliberately remains:

```text
m365_mcp.server
    -> m365_mcp.control_plane          # generic; no Planner imports
    -> planner_mcp.registration        # explicit 17-tool typed projection
    -> planner_mcp.tools               # Planner domain behavior
```

This is a staged boundary, not the final registry design. `CORE-007..010` replace the single Planner registrar with Application/Tool registries and controlled projections.

The 17 wrappers remain explicit because FastMCP input signatures are part of the compatibility surface. A dynamic/generic executor is not introduced.

## CORE-006 boundary decision

The canonical browser/session lifecycle primitive is now owned by `m365_browser_worker.browser`.

Current composition deliberately remains:

```text
m365-browser-worker entry point
    -> m365_browser_worker.app         # current Planner-compatible ASGI projection
    -> planner_browser_worker.app      # Planner semantic HTTP routes
    -> m365_browser_worker.browser     # generic browser/profile lifecycle
```

This block does not claim the Phase 3 lifecycle hardening work early. In particular:

- FastAPI lifespan ownership remains `CORE-021`;
- true browser-backed readiness remains `CORE-022`;
- Session/Capability Broker remains `CORE-023`;
- account-context enforcement remains `CORE-024`;
- controlled Microsoft egress remains `CORE-025`;
- serialized execution/queueing remains `CORE-026`;
- typed worker operation protocol remains `CORE-028`.

No generic browser primitive, raw selector/JavaScript/XPath operation, cookie/token/storage-state export or Conditional Access bypass is introduced.

## Current compatibility invariants

- Repository identity is `m365-ui-mcp`.
- Canonical Python identities are `m365_mcp` and `m365_browser_worker`.
- `M365_*` is canonical configuration; `PLANNER_*` remains a bounded alias.
- All 17 current public `planner_*` tools remain `PRESERVE` with unchanged typed signatures.
- FastMCP server name remains `planner-mcp` during this behavior-preserving extraction; product-wide projection identity changes only through a later explicit compatibility gate.
- Existing `planner_mcp_*` metric names are not renamed by CORE-006.
- State schema/path are not migrated by CORE-006.
- No Outlook capability is implemented or promoted live.
- No raw browser primitive or session-secret export is introduced.
- `CORE-025` remains mandatory before any live M365 worker egress claim.

## Next gate

```text
CORE-006 PR CI/security/images/SBOM GREEN
        -> merge
        -> post-merge main GREEN
        -> CORE-007
```
