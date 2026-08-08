# Cloudflare MCP Server Portal

Scope: how ChatGPT reaches the Planner MCP control plane through the Cloudflare MCP Server Portal and a Cloudflare Tunnel, and what the control plane assumes (and refuses to assume) about that path. Companions: [architecture.md](architecture.md), [security.md](security.md), [deployment.md](deployment.md), [threat-model.md](threat-model.md), [tool-catalog.md](tool-catalog.md).

## 1. Position in the chain

| Hop | Component | Responsibility | Trust granted |
|-----|-----------|----------------|---------------|
| 1 | ChatGPT | MCP client; issues tool calls | none |
| 2 | Cloudflare MCP Server Portal | Client-facing MCP aggregation, OAuth, per-server policy | transport + identity assertion |
| 3 | Cloudflare Tunnel (`cloudflared`) | Outbound-only connector from the host to the edge | transport only |
| 4 | `planner-mcp` control plane | Authentication, authorization, policy, idempotency, audit | authoritative |
| 5 | `planner-browser-worker` | Execution | internal only |

Design rule: the control plane treats hops 1–3 as an **untrusted transport**. Portal authentication is a necessary precondition, never a sufficient one. Every request is independently authenticated and authorized at hop 4, and every mutation is independently audited there.

## 2. Why the Portal

| Alternative | Why rejected |
|-------------|--------------|
| Publish the MCP endpoint directly | Requires inbound ports, public TLS termination on the host, and self-managed OAuth. |
| VPN to the host | Not usable from ChatGPT. |
| Reverse proxy on a VPS | Adds a second trusted machine and secret store without removing any risk. |
| Portal + Tunnel | No inbound ports, edge-terminated TLS, centralized client OAuth, per-server enable/disable, and a clean audit boundary. |

## 3. Transport

| Property | Value |
|----------|-------|
| MCP transport | Streamable HTTP (FastMCP) |
| TLS | Terminated at the Cloudflare edge; tunnel leg is Cloudflare-encrypted; host leg is loopback/`edge` bridge only |
| Inbound ports on host | **zero** |
| Connector | `cloudflared` container, egress-only, digest-pinned |
| Session semantics | Stateless per request at the transport layer; correlation is via `operation_id`, not connection identity |
| Timeouts | Client-visible tool timeout is shorter than the edge timeout so callers get a structured error rather than a connection reset |
| Streaming | Progress notifications used for long browser operations to avoid idle-timeout kills |

## 4. Identity and authorization

Two independent layers:

**Layer 1 — Portal.** Handles client OAuth, presents the Planner MCP server to authorized ChatGPT users, and can disable the server centrally. It establishes *who is calling*.

**Layer 2 — control plane.** Validates a service credential presented by the tunnel path, maps the asserted principal to an internal role, and enforces the tool policy. It establishes *what may be done*.

| Role | Tools permitted | Notes |
|------|-----------------|-------|
| `reader` | read/list/describe tools | Default role. |
| `operator` | reader + mutating tools | Requires `PLANNER_MODE=full`. |
| `maintainer` | operator + reconciliation and diagnostics | Not exposed to ChatGPT by default. |

Authorization failures return `denied` with a stable `reason` (`scope`, `readonly_mode`, `unsupported_premium`, `rate_limit`) and increment `plannermcp_tool_denied_total`. Denials are audited exactly like successes.

## 5. Portal configuration checklist

| Item | Setting | Rationale |
|------|---------|-----------|
| Server name | `planner-mcp` | Stable identifier in the Portal catalogue. |
| Endpoint | Tunnel hostname, HTTPS only | No IP literals. |
| Access policy | Explicit allowlist of principals | No "everyone in the org". |
| Session lifetime | Short, refresh required | Limits stolen-token windows. |
| Tool exposure | Only the catalogue's public subset | Diagnostics stay internal. |
| Logging | Portal-side access logs retained | Cross-checked against control-plane audit. |
| Disable switch | Documented and tested | Fast kill path. |

Tunnel configuration: single ingress rule mapping the hostname to `http://planner-mcp:8790`; a catch-all rule returning 404; no `originRequest.noTLSVerify` relaxations; connector credentials mounted read-only from a 0600 host file; connector runs non-root with `cap_drop: ALL`.

## 6. Failure modes

| Failure | Client-visible behaviour | Control-plane behaviour |
|---------|--------------------------|-------------------------|
| Portal unavailable | Tool unavailable in ChatGPT | Idle; no state change |
| Tunnel down | Connection error | Health endpoint still green on loopback; alert on connector restarts |
| Edge timeout during a long browser op | Structured timeout error | Operation continues to a terminal state, is audited, and is replay-safe via the idempotency key |
| Duplicate delivery / client retry | Same result returned | `outcome=replayed`, single mutation |
| Unauthorized principal | `denied` | Audited, metric incremented |
| Worker unreachable | Retryable error | No `ok` audit row is ever written |

The idempotency contract in [idempotency.md](idempotency.md) is what makes the untrusted transport safe: any hop may retry, and only one effect occurs.

## 7. What the Portal must never carry

| Prohibited | Reason |
|------------|--------|
| Planner credentials | Interactive login only, in the worker profile. |
| MFA approval affordances | Approval happens solely in Microsoft Authenticator. |
| Raw task content in error messages | Redaction boundary, see [privacy-boundary.md](privacy-boundary.md). |
| Worker endpoints | Worker is internal-only and never proxied. |
| Admin/metrics endpoints | Loopback only. |
| Evidence bundles | Retrieved by the operator on the host. |

## 8. Verification

| Check | Level | Expected |
|-------|-------|----------|
| No inbound host port other than loopback admin | isolated acceptance | pass |
| Unauthenticated request to the MCP endpoint | manual | rejected before any tool dispatch |
| Role enforcement matrix | contract tests | every tool × role combination asserted |
| Replay through the Portal | manual (read-only tool) | single audit row, `replayed` |
| Worker reachability from the edge network | isolated acceptance | unreachable |
| Portal disable switch | manual, per release | tool disappears from the client |

## 9. Operational notes

Rotating the tunnel token: create the new token, update the host secret file, restart only `cloudflared`, confirm connectivity with a read-only tool call, revoke the old token. The control plane is unaffected.

Changing the hostname: update the tunnel ingress and the Portal server record together; the control plane holds no hostname configuration by design, so no application redeploy is required.

Incident response: disable the server at the Portal first (fastest, client-visible), then stop `cloudflared`, then investigate. Because the worker is internal-only, cutting hop 3 fully isolates the system while leaving audit and metrics inspectable on loopback.

## 10. Backlog mapping

| Item | Backlog keys |
|------|--------------|
| Streamable HTTP endpoint + transport hardening | P-031, P-032 |
| Portal registration + access policy | P-033, P-034 |
| Role model + policy enforcement | P-035 |
| Tunnel deployment + rotation runbook | P-036, P-050 |

## 11. Client experience contract

| Aspect | Behaviour presented to ChatGPT |
|--------|-------------------------------|
| Tool names | Stable, catalogue-defined; renames are breaking changes requiring a major version |
| Descriptions | State whether a capability is mock-verified or live-verified; never overstate |
| Long operations | Progress notifications every few seconds; a final structured result |
| Errors | Public taxonomy only: `invalid_input`, `denied`, `not_found`, `conflict`, `unavailable`, `timeout`, `failed` |
| Retries | Client retries are safe; the idempotency key makes them no-ops |
| Dry run | Every mutating tool accepts `dry_run`; the response contains the computed diff summary |
| Provenance | Every response carries `operation_id`; mutations carry the read-back verdict |

## 12. Capacity and limits

| Limit | Value | Rationale |
|-------|-------|-----------|
| Concurrent tool calls | bounded by `MAX_CONCURRENCY` | One browser profile serializes UI work |
| Queue depth | alerting above 20 | Backpressure is visible rather than silent |
| Per-tool timeout | shorter than the edge timeout | Structured errors instead of resets |
| Notification rate | coalesced | Prevents alert storms via Hermes |
| Payload size | bounded request and response | Protects the worker from pathological inputs |

Because a single persistent browser profile executes all UI work, throughput is intentionally low and predictable. Scaling horizontally would require sharing the authenticated profile, which is out of scope for v1 (see [roadmap.md](roadmap.md) §12).

## 13. Change management

| Change | Required steps |
|--------|----------------|
| New tool exposed through the Portal | Catalogue entry, schema, policy rule, contract tests, Portal exposure review |
| Tool removal | Deprecation note in release notes, major version if externally referenced |
| Access policy change | Governance record naming the principals added or removed |
| Tunnel hostname change | Update the ingress and the Portal record together; no application redeploy |
| Connector upgrade | Digest bump, restart `cloudflared` only, verify with a read-only call |

## 14. Verification matrix

| Property | Test layer | Artifact |
|----------|-----------|----------|
| Transport hardening | contract (L3) | ci |
| Role enforcement | contract (L3) | ci |
| Replay safety over the transport | isolated acceptance (L6) | bundle A2 |
| No inbound host ports | isolated acceptance (L6) | bundle A2 |
| Worker unreachable from `edge` | isolated acceptance (L6) | bundle A2 |
| Portal disable switch | manual, per release | release record |
