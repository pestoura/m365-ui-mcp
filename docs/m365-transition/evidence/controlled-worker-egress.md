# CORE-025 — Controlled worker egress

## Decision

The browser worker now has a dedicated outbound network path while the control-plane/worker path remains private. No browser-worker port is published.

Outbound browser requests are additionally governed by a closed, fail-closed Microsoft 365 host-suffix policy in `m365_browser_worker.egress`. HTTPS is mandatory for network egress. Unknown hosts, deceptive suffixes and non-HTTPS schemes are aborted by the Playwright route handler before navigation continues.

## Network boundary

`browser-internal` remains `internal: true` and carries only the control-plane-to-worker path. The browser worker is also attached to `m365-egress`, which supplies the outbound route required for Microsoft 365. The control plane is not attached to `m365-egress`.

The worker still publishes no host port. Therefore adding outbound connectivity does not create a public inbound worker route.

## Application-layer egress boundary

The Playwright persistent context installs a route policy at startup. The policy permits local browser resources and reviewed HTTPS Microsoft 365 identity/shell/content domain families only. Any unreviewed host is denied by default.

Adding another external domain is a reviewed code/policy change; runtime semantic tools cannot expand the allowlist and no generic fetch/proxy/navigation primitive is exposed.

## Evidence and limitations

Automated tests prove the policy decision behavior, deceptive-domain rejection, route abort/continue behavior and Compose network topology. CI does not authenticate to a real Microsoft tenant and mock evidence remains non-live evidence.

This block establishes the controlled egress mechanism required before real-browser discovery/revalidation can be attempted. It does not by itself claim that the currently declared allowlist is complete for every Microsoft 365 tenant path; live evidence may identify additional Microsoft-owned domains that must be reviewed and added before a capability can become live-supported.

## Preserved invariants

- 17 public `planner_*` tools remain preserved.
- 11 Planner capability keys remain preserved.
- 10 historical selector keys remain preserved.
- no cookies, tokens, auth headers or storage state are exported.
- no generic browser endpoint is introduced.
- Outlook remains RESERVED with zero public tools.
