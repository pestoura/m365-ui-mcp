# PLN-MIG-006 — Preserve `planner_*` public tool names

Status: **PREIMPLEMENTED_STACKED_AWAITING_PLN_MIG_005**

## Objective

Make the Planner public MCP naming surface an explicit application-owned compatibility ABI and prove that the M365 migration preserves all 17 historical `planner_*` names in canonical order.

## Canonical surface

`m365_mcp.apps.planner.public_surface` defines the immutable `PLANNER_PUBLIC_TOOL_NAMES` tuple containing exactly the 17 current public names.

The contract preserves:

- exact spelling;
- exact `planner_*` prefix;
- exact count of 17 tools;
- deterministic historical order;
- no Outlook or generic browser/executor name exposure.

## Compatibility enforcement

Acceptance tests compare the canonical application-owned ABI against:

- the current Planner Tool Registry projection;
- the legacy `planner_mcp.tools.TOOL_NAMES` compatibility surface;
- the `PRESERVE` compatibility requirement on every Planner Tool Registry definition.

A rename, removal, addition, reorder or compatibility downgrade therefore fails the migration gate rather than silently changing the public API.

## Safety boundary

PLN-MIG-006 changes no tool behavior, schemas, worker operation, policy decision or mutation state. It enables no Outlook tool and introduces no browser primitive.

## Dependency gate

This work is stacked on PLN-MIG-005. It must not merge until PLN-MIG-005 is merged and post-merge `main` is GREEN. It will then be retargeted to `main` and fully revalidated with all mandatory CI/security/image/Trivy/SBOM/documentation gates.
