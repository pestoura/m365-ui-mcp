# Architecture

## 1. Canonical topology

```
+---------------------------+
| MCP client (ChatGPT)      |
+-------------+-------------+
              | MCP (streamable HTTP)
+-------------v-------------+
| Cloudflare MCP Server     |  edge identity, exposure, rate limiting, audit
| Portal                    |
+-------------+-------------+
              | authenticated tunnel, no public origin
+-------------v-------------+
| Planner MCP control plane |  tools, policy, state, reconciliation, observability
+-------------+-------------+
              | private RPC (loopback / private network only)
+-------------v-------------+
| planner-browser-worker    |  session owner, UIContract, evidence capture
+-------------+-------------+
              | CDP
+-------------v-------------+
| Playwright / Chromium     |  isolated persistent professional profile
+-------------+-------------+
              | HTTPS (human-authenticated session)
+-------------v-------------+
| Planner Premium UI        |  system of record
+---------------------------+

Hermes  --(notifications, HITL prompts, approval signalling)--  control plane
        never in the MFA path, never holds credentials
```

## 2. Planes

| Plane | Component | Responsibility | Never does |
|---|---|---|---|
| Edge | Cloudflare MCP Portal | exposure, client identity, transport policy | business logic |
| Control | Planner MCP | semantic tools, policy decisions, desired state, idempotency, reconciliation, metrics/logs | own a browser, hold a password |
| Execution | planner-browser-worker | drive the UI, enforce UIContract, capture evidence, own session lifecycle | be publicly reachable, expose raw input |
| Rendering | Chromium (persistent profile) | authenticated session state | be shared with personal browsing |
| Out of band | Hermes | notify human, carry sanitized HITL payloads | approve MFA, transport secrets |

Control/worker separation is a decision, not an implementation detail:
[ADR-002](adr/ADR-002-control-plane-worker-separation.md).

## 3. Request lifecycle

1. **Admission** — Portal authenticates the MCP client; control plane validates tool name and schema.
2. **Policy** — policy engine returns `ALLOW`, `DENY` or `REQUIRE_APPROVAL`
   from `mutation_class`, `trust_level`, `attestation_status` and capability state.
3. **Readiness** — `planner_readiness` semantics: auth state must be `AUTHENTICATED`;
   UIContract for the touched surfaces must be `valid`.
4. **Plan** — for mutations, a desired-state delta is computed against last observed state.
5. **Execute** — worker performs the semantic operation under a scoped lock.
6. **Read-back** — worker re-reads the affected entity from the UI. No read-back, no success.
7. **Settle** — state store records observed state, evidence refs, idempotency key result.
8. **Report** — structured redacted JSON log, metrics, tool response with attestation metadata.

Any step may raise a **blocker**; blockers stop the pipeline and are returned verbatim to the caller
in a machine-readable form (see [state-model.md](state-model.md)).

## 4. Components in detail

### 4.1 Control plane
- Tool registry built from `ToolManifest` / `ExtendedToolManifest` (see [tool-catalog.md](tool-catalog.md)).
- Policy engine (see [governance.md](governance.md)).
- State store: desired state, observed state, idempotency ledger, approval ledger, attestation ledger.
- Reconciler: plan/apply/verify loop (see [reconciliation.md](reconciliation.md)).
- Observability: structured logs + low-cardinality metrics (see [observability.md](observability.md)).

### 4.2 Browser worker
- Single-owner of the Chromium persistent profile; serialized per-profile access.
- UIContract validation before any interaction (see [ui-contract.md](ui-contract.md)).
- Evidence capture: DOM extracts, screenshots, selector fingerprints — all redacted.
- Auth state machine owner (see [authentication-and-mfa.md](authentication-and-mfa.md)).
- Not publicly routable; no raw `click`/`type`/`navigate` reachable from MCP.
  ([ADR-001](adr/ADR-001-browser-automation.md))

### 4.3 Persistence
| Store | Contents | Retention |
|---|---|---|
| session profile | Chromium cookies/storage for the professional identity | until expiry/revocation |
| state store | desired/observed entity state, `external_id`/`source_id` mapping | project lifetime |
| idempotency ledger | key -> outcome, non-replayable | bounded, see [idempotency.md](idempotency.md) |
| approval ledger | persistent, non-replayable approvals | audit lifetime |
| attestation ledger | UIContract + capability attestations with timestamps | audit lifetime |
| evidence store | redacted DOM/screenshot artefacts keyed by `operation_id` | bounded retention |

## 5. Trust zones

- **Zone E (edge/public)**: Cloudflare Portal. Untrusted clients.
- **Zone C (control)**: Planner MCP. Trusted logic, no secrets beyond operational config.
- **Zone W (execution)**: worker + Chromium profile. **Highest sensitivity**: holds live session.
- **Zone H (human)**: password, Authenticator, approvals. Never crossed by software.

Traffic is only ever E -> C -> W. W never calls out to E. Hermes attaches to C only.

## 6. Failure posture

Fail closed. Concretely: unknown selector -> `UI_DRIFT`; ambiguous session -> re-run auth status,
never assume; policy engine error -> `DENY`; read-back mismatch -> mark operation `UNVERIFIED`
and do not retry blindly (see [idempotency.md](idempotency.md) read-back-before-retry rule).
