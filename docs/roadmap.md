# Roadmap

Scope: delivery phases for `pestoura/planner-mcp`, aligned one-to-one with EPIC-01..EPIC-10 and the backlog keys P-001..P-074. Companions: [backlog.md](backlog.md), [architecture.md](architecture.md), [release-process.md](release-process.md), [acceptance.md](acceptance.md), [traceability.md](traceability.md).

Sequencing rule: the browser worker is the product. Phases are ordered so that a *browser-evidenced* Planner mutation exists as early as possible, and every later phase hardens, observes, or governs that path. Microsoft Graph work is contextual enrichment and is deliberately scheduled late and kept optional.

## 0. Phase map

| Phase | Epic | Theme | Backlog | Exit artifact |
|-------|------|-------|---------|---------------|
| P0 | EPIC-01 | Specification and ADR foundation | P-001..P-010 | Approved doc set + ADRs |
| P1 | EPIC-02 | Control-plane skeleton (FastMCP) | P-011..P-017 | Discoverable, schema-valid tool surface |
| P2 | EPIC-03 | Browser worker skeleton | P-018..P-024 | Worker executes a read against the mock UI |
| P3 | EPIC-04 | Execution semantics: state, read-back, idempotency | P-025..P-030 | Verified mutation on the mock UI |
| P4 | EPIC-05 | Transport and Portal exposure | P-031..P-036 | Reachable from ChatGPT via the Portal |
| P5 | EPIC-06 | Hermes notifications and HITL | P-037..P-045 | Sanitized MFA event + working HITL gate |
| P6 | EPIC-07 | Observability, audit, alerting | P-046..P-053 | Redacted logs, metrics, hash-chained audit |
| P7 | EPIC-08 | Test architecture and mock Planner UI | P-054..P-060 | Full L1–L5 suites green in CI |
| P8 | EPIC-09 | Deployment hardening and supply chain | P-061..P-067 | Hardened, digest-pinned compose stack |
| P9 | EPIC-10 | Acceptance, reporting, release governance | P-068..P-074 | Evidence bundles + capability matrix + live read-only attestation |

## 1. Phase P0 — Specification foundation (EPIC-01, P-001..P-010)

Objective: make every subsequent decision cheap by fixing scope, boundaries and contracts first.

| Item | Deliverable |
|------|-------------|
| P-001 | Vision, scope and the browser-primary/Graph-contextual principle |
| P-002 | Architecture and the four-hop chain |
| P-003 | Threat model |
| P-004 | Security model and privacy boundary |
| P-005 | Authentication and MFA policy (Authenticator-only approval) |
| P-006 | Planner Premium capability inventory |
| P-007 | Tool catalogue and error taxonomy |
| P-008 | UI contract and selector registry design |
| P-009 | State model, reconciliation and idempotency specifications |
| P-010 | Governance, ADR process, backlog and roadmap |

Exit gates: all documents cross-linked; each ADR has status, context, decision, consequences; backlog keys assigned; critical path published. No code merges before P0 exit.

## 2. Phase P1 — Control-plane skeleton (EPIC-02, P-011..P-017)

| Item | Deliverable |
|------|-------------|
| P-011 | FastMCP application bootstrap, config loading, fail-closed startup assertions |
| P-012 | Tool registration framework driven by the catalogue |
| P-013 | Input/output schema layer with `additionalProperties: false` |
| P-014 | Policy layer: roles, read-only mode, dry-run, denial taxonomy |
| P-015 | Worker client interface + contract double |
| P-016 | Health/readiness endpoints on loopback |
| P-017 | Structured logging skeleton wired to the redaction factory |

Exit gates: every catalogued tool discoverable and schema-validated; mutating tools refuse to execute without a worker; L1–L3 suites green.

## 3. Phase P2 — Browser worker skeleton (EPIC-03, P-018..P-024)

| Item | Deliverable |
|------|-------------|
| P-018 | FastAPI worker service, internal-only binding |
| P-019 | Playwright/Chromium lifecycle with persistent profile volume |
| P-020 | Navigation layer with URL allowlist and surface model |
| P-021 | Selector registry implementation with primary + fallback strategies |
| P-022 | Read operations for plan/bucket/task |
| P-023 | Session state machine (`cold`→`warming`→`ready`/`mfa_required`/`expired`) |
| P-024 | Worker error taxonomy and retry policy |

Exit gates: worker performs reads against the mock UI; zero selector misses in mock attestation; worker unreachable from the host.

## 4. Phase P3 — Execution semantics (EPIC-04, P-025..P-030)

The most important phase: it turns navigation into trustworthy mutation.

| Item | Deliverable |
|------|-------------|
| P-025 | Normalized state model implementation for Planner Premium fields |
| P-026 | Read-back verifier with guard fields and `indeterminate`=failure |
| P-027 | Mutation pipeline (`plan`→`precondition`→`act`→`read_back`→`finalize`) |
| P-028 | Reconciliation engine, drift classification |
| P-029 | Reconciliation reporting |
| P-030 | Idempotency store, key derivation, replay/conflict semantics |

Exit gates: mutations on the mock UI verified by read-back; replay produces exactly one effect; injected read-back mismatch fails loudly.

## 5. Phase P4 — Transport and Portal (EPIC-05, P-031..P-036)

| Item | Deliverable |
|------|-------------|
| P-031 | Streamable HTTP endpoint hardening, timeouts, progress notifications |
| P-032 | Transport-level authentication independent of the Portal |
| P-033 | Portal server registration and access policy |
| P-034 | Cloudflare Tunnel deployment, egress-only connector |
| P-035 | Role model enforcement matrix |
| P-036 | Token rotation runbook |

Exit gates: a read-only tool call succeeds end-to-end from ChatGPT; unauthenticated calls rejected before dispatch; zero inbound host ports beyond loopback admin.

## 6. Phase P5 — Hermes notifications and HITL (EPIC-06, P-037..P-045)

| Item | Deliverable |
|------|-------------|
| P-037 | Sanitized MFA event schema (5 fields, closed) |
| P-038 | MFA event emission wired to the session state machine |
| P-039 | Notification transport with bearer auth |
| P-040 | Rate limiting and coalescing |
| P-041 | HITL request generation from dry-run diffs |
| P-042 | HITL callback endpoint, loopback-bound |
| P-043 | Approval binding to a specific diff + expiry default-reject |
| P-044 | HMAC, timestamp window, nonce replay protection |
| P-045 | Integration metrics and alerts |

Exit gates: no Planner content in any outbound payload during a full scenario run; HITL timeout defaults to reject; Hermes disabled ⇒ gated tools denied, others unaffected.

## 7. Phase P6 — Observability and audit (EPIC-07, P-046..P-053)

| Item | Deliverable |
|------|-------------|
| P-046 | Log record schema |
| P-047 | Redaction factory + detector suite |
| P-048 | Metrics registry with enumerated labels |
| P-049 | Cardinality guard failing startup on violation |
| P-050 | OpenTelemetry propagation across all four hops |
| P-051 | Audit store, append-only grants |
| P-052 | Hash chaining + verifier job |
| P-053 | Alert rules and runbooks |

Exit gates: redaction suite green with zero skips; audit chain verifies; alerts fire in a fault-injection drill.

## 8. Phase P7 — Test architecture (EPIC-08, P-054..P-060)

| Item | Deliverable |
|------|-------------|
| P-054 | Unit/schema harness, injected clock and id factory |
| P-055 | Fixture management and orphan-fixture check |
| P-056 | Contract suite for MCP surface |
| P-057 | Dual-run contract testing (double vs real worker) |
| P-058 | Mock Planner UI application |
| P-059 | Mock-UI Playwright suites incl. failure modes |
| P-060 | Selector attestation sub-layers A–C |

Exit gates: CI proven incapable of reaching a live tenant (egress denial, env guard, allowlist, static grep); coverage thresholds met; zero flakes over three consecutive runs.

## 9. Phase P8 — Deployment hardening (EPIC-09, P-061..P-067)

| Item | Deliverable |
|------|-------------|
| P-061 | Compose topology with `worker-net` internal |
| P-062 | Loopback vs public boundary enforcement |
| P-063 | Non-root, read-only FS, `cap_drop: ALL`, `no-new-privileges`, tmpfs sizing |
| P-064 | Compose-lint CI job (docker socket, host mounts, privileged, tags) |
| P-065 | Digest pinning for images and Dockerfile bases |
| P-066 | SBOM generation and diff gate |
| P-067 | Secrets handling, file mounts, permission assertions |

Exit gates: every prohibition in [deployment.md](deployment.md) is machine-enforced; stack starts with all hardening flags; profile volume isolation verified.

## 10. Phase P9 — Acceptance, reporting, release governance (EPIC-10, P-068..P-074)

| Item | Deliverable |
|------|-------------|
| P-068 | Report generator framework and schemas |
| P-069 | Operational digest, selector drift report, attestation history |
| P-070 | Evidence bundle format, manifest, hashing |
| P-071 | Isolated acceptance harness (A2) |
| P-072 | Evidence index and release record integration |
| P-073 | Live read-only mode and operator protocol (A3) |
| P-074 | Capability matrix automation + CI gate blocking unsupported claims |

Exit gates: A2 passes for every pre-release scenario; a live read-only attestation with zero misses exists before any live-support claim; capability matrix generated, never hand-edited.

## 11. Critical path

`P-001 → P-011 → P-014 → P-018 → P-025 → P-026 → P-027 → P-030 → P-031 → P-050 → P-069 → P-071 → P-073 → P-074`

| Segment | Meaning |
|---------|---------|
| P-001 → P-011 | Specification before code. |
| P-011 → P-014 | A tool surface is worthless without policy. |
| P-014 → P-018 | Policy needs an executor. |
| P-018 → P-025 → P-026 → P-027 | Navigation → normalized state → verification → verified mutation. |
| P-027 → P-030 | Verified mutation must be replay-safe. |
| P-030 → P-031 | Only then is public exposure responsible. |
| P-031 → P-050 | Exposure requires end-to-end correlation. |
| P-050 → P-069 → P-071 | Correlation enables reporting, which enables acceptance. |
| P-071 → P-073 → P-074 | Isolated acceptance precedes live read-only, which alone permits capability claims. |

Any slip on a critical-path item slips the release date one-for-one; non-critical items may be deferred to a later phase with a governance note.

## 12. Deferred and explicitly out of scope

| Item | Status | Rationale |
|------|--------|-----------|
| Live mutating acceptance automation (A4) | Deferred indefinitely | Manual, per-operation approval by design. |
| Graph-based write paths | Out of scope | Would violate the browser-primary principle. |
| Multi-tenant operation | Out of scope for v1 | Single persistent profile per deployment. |
| Horizontal worker scaling | Deferred | Requires profile-sharing design with unresolved security implications. |
| Attachment upload/download | Deferred to post-v1 | Content handling expands the privacy boundary materially. |
| Webhook-driven real-time sync | Deferred | Reconciliation polling is sufficient for v1. |
