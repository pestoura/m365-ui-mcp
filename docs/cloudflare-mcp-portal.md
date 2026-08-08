# Cloudflare MCP Server Portal

This document defines the intended external exposure boundary for Planner MCP:

```text
ChatGPT
   ↓
Cloudflare MCP Server Portal / protected Cloudflare ingress
   ↓
Planner MCP Control Plane
```

The private browser worker remains outside the public ingress path.

Companions: [`architecture.md`](architecture.md), [`security.md`](security.md),
[`deployment.md`](deployment.md), [`tool-catalog.md`](tool-catalog.md) and
[`release-process.md`](release-process.md).

## 1. Trust boundary

Cloudflare provides transport/edge controls. It is not the Planner MCP authorization authority.
The control plane independently validates the request/identity/context required by its policy before
dispatching any semantic tool.

Principles:

- no direct public browser-worker endpoint;
- no direct public Chromium/DevTools endpoint;
- no public admin/metrics/state/evidence endpoint;
- origin access restricted to the approved Cloudflare path where the deployment supports it;
- TLS required;
- authorization/policy enforced again at the control plane;
- request limits/rate limits/backpressure are explicit;
- transport retries must not create duplicate effects in later mutation releases.

## 2. MCP transport

The control plane uses FastMCP Streamable HTTP as its client-facing MCP transport.

Requirements:

- stable MCP endpoint;
- bounded request/response sizes;
- explicit timeouts compatible with browser operations;
- structured public error taxonomy;
- health/readiness kept separate from the MCP tool endpoint as appropriate to deployment;
- no raw worker/browser URL or selector exposure in public errors;
- tool descriptions reflect evidence state truthfully.

For 0.1.0, the exposed MCP registry contains exactly the canonical 17 `READ` tools.

## 3. Authentication and authorization

The final Cloudflare client-auth mechanism may be environment-specific, but the product boundary is
stable:

1. Cloudflare/Portal authenticates or constrains the client according to the configured edge policy;
2. the origin receives only the minimum trusted identity/service assertion required by the design;
3. Planner MCP maps that assertion to internal authorization context;
4. policy evaluates the exact tool/operation;
5. denied/ambiguous/invalid context fails closed before worker dispatch.

No edge setting can automatically grant a mutation the control plane policy would deny.

In 0.1.0, read-only mode means no mutation tool exists in the public registry, regardless of the
caller role.

## 4. Origin protection

The deployment should ensure, as supported by the chosen Cloudflare product/configuration:

- origin not generally reachable from the public internet;
- tunnel/connector outbound from the host rather than opening unnecessary inbound ports;
- explicit hostname/ingress mapping;
- default-deny/catch-all behavior for unmatched ingress;
- connector credentials stored as infrastructure secrets, not repository config;
- connector container/service hardened consistently with the deployment baseline;
- origin authentication/validation is not disabled for convenience.

The exact operational configuration is evidence-bearing deployment state and must be documented when
implemented; this specification does not invent tenant-specific Cloudflare values.

## 5. Rate limiting and backpressure

Browser automation is capacity-constrained by design. Protect the origin using:

- bounded concurrent MCP calls;
- bounded queue depth;
- per-client/per-server rate controls where available;
- response on overload rather than unbounded queueing;
- operation deadlines shorter than infrastructure hard timeouts where practical;
- progress semantics for legitimately long operations when supported by the MCP/runtime contract.

A client timeout does not prove that a later mutation failed. Later write releases rely on
idempotency + read-back to resolve that uncertainty.

## 6. Public data boundary

The public MCP path may carry semantic request/response data required by the tool contract, but never:

- Microsoft password;
- access/refresh token;
- exported cookies/browser storage;
- browser profile content;
- internal worker endpoint;
- raw CSS/XPath/DOM debugging material;
- private keys/HMAC secret values;
- unrestricted audit/state database content.

Errors are sanitized and expose stable codes, not internal stack traces or browser HTML.

## 7. MFA

When the browser detects number-matching MFA, the service may emit a separate sanitized notification
through Hermes according to its contract. Cloudflare/ChatGPT must not expose an MFA-approval action.

Approval occurs only in Microsoft Authenticator.

## 8. Failure modes

| Failure | Required behavior |
| --- | --- |
| Cloudflare/Portal unavailable | MCP unavailable; no state change inferred |
| tunnel/connector down | external calls unavailable; local service may remain healthy |
| unauthorized/invalid client context | deny before tool dispatch |
| origin policy invalid | fail closed |
| browser worker unavailable | return bounded `unavailable`/typed error; no fake success |
| client timeout | preserve operation state; later writes resolve outcome via read-back/idempotency |
| rate limit | bounded retryable response according to policy; no unbounded queue |

## 9. Verification

Required verification when Cloudflare exposure is implemented:

- MCP endpoint is reachable through the intended Cloudflare path;
- direct/unapproved origin path is rejected/unavailable according to deployment design;
- unauthenticated/unauthorized request is rejected before worker dispatch;
- worker/admin/metrics endpoints are not exposed through the ingress;
- exact 0.1.0 public tool registry remains read-only;
- request size/rate/backpressure controls behave as documented;
- sanitized public errors contain no secrets/internal browser material;
- read-only smoke call works end-to-end after deployment.

These checks become release evidence, not merely setup instructions.

## 10. Operational actions

Documented runbooks should include:

- connector credential rotation;
- hostname/ingress change;
- disable/kill switch;
- connector upgrade by exact digest;
- origin connectivity troubleshooting;
- rate-limit/backpressure tuning;
- read-only post-deploy smoke verification.

Changes to Cloudflare settings that alter trust/identity/origin exposure require security review and,
if architectural, an ADR.

## 11. Backlog/traceability ownership

There is no separate Cloudflare EPIC in the canonical P-001..P-074 backlog. Cloudflare exposure is a
cross-cutting deployment requirement linked to existing owners:

| Concern | Canonical P-key(s) |
| --- | --- |
| FastMCP Streamable HTTP foundation | P-007 |
| error taxonomy / safe public errors | P-010 |
| policy/default-deny | P-061 |
| container/deployment posture | P-064 |
| complete CI | P-068 |
| isolated/end-to-end acceptance | P-069 |
| release process/deployment smoke | P-073, P-074 |

A future requirement that needs substantial new Cloudflare-specific implementation must be added to
the backlog explicitly rather than silently repurposing P-031..P-036.
