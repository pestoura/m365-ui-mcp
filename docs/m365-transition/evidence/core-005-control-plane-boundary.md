# CORE-005 — Generic control-plane package boundary

## Goal

Separate application-neutral FastMCP construction from Planner domain implementation without changing the immutable Planner 0.1.0 public behavior.

## Implemented boundary

`m365_mcp.control_plane` creates the FastMCP server and invokes an injected semantic registrar. It does not import Planner, Outlook, browser locators or any application-specific operation.

Planner-specific registration now lives in `planner_mcp.registration`. It retains explicit typed wrappers for every current public tool so FastMCP input schemas remain stable.

The canonical composition root `m365_mcp.server` currently selects the Planner registrar directly. This is intentionally temporary: `CORE-007` introduces the Application Registry and `CORE-008..010` introduce canonical tool metadata and controlled projections.

## Non-goals

CORE-005 does not:

- change the 17 public `planner_*` names or signatures;
- create Outlook tools;
- create a generic browser or generic MCP executor;
- move browser-worker lifecycle code;
- migrate the state database/schema/path;
- rename existing Prometheus metric series;
- generalize the current Planner contracts/manifests;
- change policy, approvals, idempotency or sagas;
- claim live Planner support.

## Security properties

The extracted runtime can only receive a registrar callable; it does not expose arbitrary browser actions, code execution or selector injection. Application code remains responsible for semantic closed operations and the existing policy boundary.

A structural unit test parses the generic runtime imports and fails if `planner_mcp` is introduced into that module.

## Compatibility evidence required

Before merge:

1. all existing Planner server/tool tests pass;
2. `planner_mcp.server.build_server` resolves to the canonical M365 composition function;
3. the public catalog remains exactly the same 17 `planner_*` tools;
4. compile/lint/mypy/contracts/release/isolated acceptance pass;
5. dependency/secret scans pass;
6. both container builds and HIGH/CRITICAL Trivy gates pass;
7. both CycloneDX SBOMs validate.

Post-merge the same applicable gates must execute again before CORE-006 starts.
