# Traceability

Scope: the mapping from requirements → architecture/ADR → backlog keys → tests and evidence for `pestoura/planner-mcp`. This document is the audit surface for "why does this code exist and what proves it works". Companions: [roadmap.md](roadmap.md), [backlog.md](backlog.md), [testing.md](testing.md), [acceptance.md](acceptance.md), [release-process.md](release-process.md).

Maintenance rule: any PR that changes a requirement, adds an ADR, adds a tool, or changes a test mapping must update this table in the same PR (gate G10 of the release process).

## 1. Legend

| Column | Meaning |
|--------|---------|
| Req | Requirement id, `R-nn`. |
| Requirement | Normative statement. |
| Architecture / ADR | Where the decision lives. |
| Backlog | P-keys implementing it. |
| Tests | Layers per [testing.md](testing.md): L1 unit, L2 schema, L3 contract, L4 mock UI, L5 attestation, L6 isolated acceptance, L7 live. |
| Evidence | Artifact proving satisfaction. |

Evidence types: `bundle` = acceptance evidence bundle; `attest` = selector attestation report; `ci` = pipeline artifact; `audit` = audit export; `matrix` = capability matrix row.

## 2. Core product requirements

| Req | Requirement | Architecture / ADR | Backlog | Tests | Evidence |
|-----|-------------|--------------------|---------|-------|----------|
| R-01 | Planner operations are performed primarily by a private Chromium/Playwright browser worker. | [architecture.md](architecture.md) §chain; ADR-0001 | P-001, P-018, P-019 | L4, L6 | bundle A2 |
| R-02 | Microsoft Graph is contextual only and never gates functionality. | ADR-0002 | P-001, P-022 | L1, L3, L6 (Graph-disabled run) | bundle A2 |
| R-03 | Exposure to ChatGPT is via the Cloudflare MCP Server Portal over a tunnel with zero inbound host ports. | [cloudflare-mcp-portal.md](cloudflare-mcp-portal.md); ADR-0003 | P-031..P-036 | L3, L6 | bundle A2, deployment record |
| R-04 | The control plane speaks MCP over FastMCP Streamable HTTP. | [architecture.md](architecture.md); ADR-0004 | P-011, P-031 | L3 | ci |
| R-05 | The browser worker is reachable only from the internal network. | [deployment.md](deployment.md) §2; ADR-0005 | P-018, P-061 | L6 (reachability assertion) | bundle A2 |
| R-06 | Every mutation is verified by a UI read-back and fails on divergence. | [acceptance.md](acceptance.md) §5; ADR-0006 | P-026, P-027 | L1, L4, L6 | bundle A2, audit |
| R-07 | Every mutating tool is idempotent under key replay. | [idempotency.md](idempotency.md); ADR-0007 | P-030 | L1, L3, L6 | bundle A2 |
| R-08 | Every mutating tool supports `dry_run` with zero side effects. | [tool-catalog.md](tool-catalog.md) | P-014, P-027 | L3, L6 | bundle A2 |
| R-09 | State is normalized before comparison. | [state-model.md](state-model.md) | P-025 | L1, L4 | ci |
| R-10 | Drift is classified exhaustively and reported. | [reconciliation.md](reconciliation.md) | P-028, P-029 | L1, L6 | bundle A2, report |

## 3. Security and privacy requirements

| Req | Requirement | Architecture / ADR | Backlog | Tests | Evidence |
|-----|-------------|--------------------|---------|-------|----------|
| R-11 | No credential, PII, or business content appears in logs, metrics, traces, or reports. | [privacy-boundary.md](privacy-boundary.md); ADR-0008 | P-046, P-047 | L1 (detector), L6 | bundle A2 |
| R-12 | Metrics labels are drawn from closed enumerations; cardinality is bounded. | [observability.md](observability.md) §4 | P-048, P-049 | L1, startup assertion | ci |
| R-13 | The audit trail is append-only and hash-chained. | [observability.md](observability.md) §6; ADR-0009 | P-051, P-052 | L1, L6 (chain verify) | audit |
| R-14 | MFA approval occurs only in Microsoft Authenticator. | [authentication-and-mfa.md](authentication-and-mfa.md); ADR-0010 | P-037, P-038 | L2, L6 | bundle A2 |
| R-15 | The sanitized MFA event carries exactly five fields. | [hermes-integration.md](hermes-integration.md) §3 | P-037 | L2 (closed schema) | ci |
| R-16 | Hermes is limited to notifications and HITL and cannot mutate Planner. | [hermes-integration.md](hermes-integration.md) | P-039..P-045 | L3, L6 | bundle A2 |
| R-17 | HITL fails closed: no answer means no mutation. | [hermes-integration.md](hermes-integration.md) §4 | P-043 | L3 | ci |
| R-18 | HITL responses are replay-protected. | [security.md](security.md) | P-044 | L1, L3 | ci |
| R-19 | Secrets are file-mounted, never baked into images or logged. | [deployment.md](deployment.md) §8 | P-067 | L1, G8 lint | ci |
| R-20 | Session profile material never leaves the worker volume. | [security.md](security.md); ADR-0011 | P-019, P-063 | L6 (mount assertions) | bundle A2 |
| R-21 | Every request is authorized at the control plane independently of the Portal. | [cloudflare-mcp-portal.md](cloudflare-mcp-portal.md) §4 | P-014, P-032, P-035 | L3 (role matrix) | ci |
| R-22 | Threat-model mitigations are implemented or explicitly accepted. | [threat-model.md](threat-model.md) | P-003, P-063..P-067 | review | governance log |

## 4. Runtime and deployment requirements

| Req | Requirement | Architecture / ADR | Backlog | Tests | Evidence |
|-----|-------------|--------------------|---------|-------|----------|
| R-23 | All containers run non-root with a read-only root filesystem. | [deployment.md](deployment.md) §4 | P-063 | G8 lint, L6 | ci, bundle A2 |
| R-24 | All containers drop every capability and set `no-new-privileges`. | [deployment.md](deployment.md) §4 | P-063 | G8 lint | ci |
| R-25 | Writable paths are explicit tmpfs or named volumes with size limits. | [deployment.md](deployment.md) §5 | P-063 | G8 lint | ci |
| R-26 | No Docker socket or host home/root mounts anywhere. | [deployment.md](deployment.md) §4 | P-064 | G8 lint | ci |
| R-27 | Only the loopback admin port is published on the host. | [deployment.md](deployment.md) §3 | P-062 | G8 lint, L6 | bundle A2 |
| R-28 | All images and Dockerfile bases are digest-pinned; CI enforces it. | [deployment.md](deployment.md) §7 | P-065 | G8 lint | ci |
| R-29 | An SBOM is produced and diffed per release. | [release-process.md](release-process.md) §6 | P-066 | G7 | SBOM artifact |
| R-30 | The stack fails closed on invalid configuration. | [deployment.md](deployment.md) §9 | P-011, P-063 | L1, L6 | ci |

## 5. Quality and governance requirements

| Req | Requirement | Architecture / ADR | Backlog | Tests | Evidence |
|-----|-------------|--------------------|---------|-------|----------|
| R-31 | CI never mutates a live Planner tenant. | [testing.md](testing.md) §0; ADR-0012 | P-057, P-058 | G4 safety assertions | ci |
| R-32 | Browser-level CI testing runs against a mock Planner UI. | [testing.md](testing.md) §5 | P-058, P-059 | L4 | ci |
| R-33 | Every logical selector is attested structurally and semantically. | [testing.md](testing.md) §6 | P-060 | L5 A–C | attest |
| R-34 | Live verification is manual and read-only initially. | [acceptance.md](acceptance.md) §6 | P-073 | L7 | attest, bundle A3 |
| R-35 | Live support is never claimed without live browser evidence. | [release-process.md](release-process.md) §11 | P-074 | CI matrix gate | matrix |
| R-36 | Isolated acceptance passes before every release. | [acceptance.md](acceptance.md) §4 | P-071 | L6 | bundle A2 |
| R-37 | Evidence bundles are immutable and hash-verified. | [acceptance.md](acceptance.md) §3 | P-070 | L2, L6 | bundle manifest |
| R-38 | Every PR references a backlog key and updates traceability. | [governance.md](governance.md) | P-010 | review | PR record |
| R-39 | Reports never exceed the redaction boundary. | [reporting.md](reporting.md) | P-068, P-069 | L1, L6 | ci |
| R-40 | Alerts exist for every failure mode that requires human action. | [observability.md](observability.md) §7 | P-053 | fault-injection drill | drill record |

## 6. Critical-path traceability

The critical path from [roadmap.md](roadmap.md), with the requirement each hop satisfies and the evidence that closes it.

| Order | Key | Requirement(s) | Deliverable | Closing evidence |
|-------|-----|----------------|-------------|------------------|
| 1 | P-001 | R-01, R-02 | Specification: browser-primary, Graph-contextual | Approved docs + ADR-0001/0002 |
| 2 | P-011 | R-04, R-30 | FastMCP control plane bootstrap | ci (G1–G4) |
| 3 | P-014 | R-08, R-21 | Policy layer: roles, read-only, dry-run | L3 role matrix |
| 4 | P-018 | R-05 | Worker service, internal-only | L6 reachability assertion |
| 5 | P-025 | R-09 | Normalized state model | L1 + L4 |
| 6 | P-026 | R-06 | Read-back verifier | L4 + injected-mismatch scenario |
| 7 | P-027 | R-06, R-08 | Mutation pipeline | bundle A2 |
| 8 | P-030 | R-07 | Idempotency store and replay semantics | bundle A2 replay scenario |
| 9 | P-031 | R-03 | Streamable HTTP + tunnel exposure | deployment record + smoke call |
| 10 | P-050 | R-12, R-13 | Trace propagation across all hops | ci + bundle A2 traces |
| 11 | P-069 | R-39, R-40 | Operational and drift reporting | report artifacts |
| 12 | P-071 | R-36 | Isolated acceptance harness | bundle A2 |
| 13 | P-073 | R-34 | Live read-only protocol | bundle A3 + attest (miss == 0) |
| 14 | P-074 | R-35 | Capability matrix automation and gate | matrix + CI gate |

Interpretation: hops 1–8 build a *trustworthy* mutation; hop 9 exposes it; hop 10 makes it explainable; hops 11–14 make claims about it provable. A claim of live support that skips hops 12–14 is invalid by construction.

## 7. Epic ↔ requirement coverage

| Epic | Backlog | Requirements covered |
|------|---------|----------------------|
| EPIC-01 | P-001..P-010 | R-01, R-02, R-22, R-38 |
| EPIC-02 | P-011..P-017 | R-04, R-08, R-21, R-30 |
| EPIC-03 | P-018..P-024 | R-05, R-20 |
| EPIC-04 | P-025..P-030 | R-06, R-07, R-09, R-10 |
| EPIC-05 | P-031..P-036 | R-03, R-21 |
| EPIC-06 | P-037..P-045 | R-14..R-18 |
| EPIC-07 | P-046..P-053 | R-11, R-12, R-13, R-40 |
| EPIC-08 | P-054..P-060 | R-31, R-32, R-33 |
| EPIC-09 | P-061..P-067 | R-19, R-23..R-30 |
| EPIC-10 | P-068..P-074 | R-34..R-37, R-39 |

Every requirement maps to at least one epic, and every epic carries at least one requirement; a gap in either direction is a governance defect and blocks the release.

## 8. Verification of this document

| Check | Mechanism |
|-------|-----------|
| Every P-key referenced here exists in the backlog | CI script |
| Every backlog key appears in at least one row of §2–§5 or §7 | CI script |
| Every relative doc link resolves | link checker (G2) |
| Every evidence type referenced is produced by a real gate | review at G10 |
| Critical path here matches the roadmap | CI string comparison |

## 9. Coverage gaps and accepted risks

| Gap | Requirement affected | Status | Owner action |
|-----|----------------------|--------|--------------|
| Live mutating acceptance is manual only | R-06, R-34 | accepted | Documented in [roadmap.md](roadmap.md) §12; no automation planned |
| Real Planner DOM may change without notice | R-33 | mitigated | Selector drift report + freeze procedure |
| Single browser profile is a single point of failure | R-01 | accepted | Documented capacity limit; re-auth runbook |
| Graph schema drift | R-02 | low impact | Contextual only; degrades to `available=false` |
| Attachment handling not implemented | — | out of scope | Deferred post-v1 |

Accepted risks carry an owner and are re-reviewed at each epic closure; an accepted risk that gains a viable mitigation becomes a backlog item rather than remaining accepted.

## 10. How to use this document

| Question | Where to look |
|----------|---------------|
| "Why does this module exist?" | Find the P-key in §2–§5; read the requirement. |
| "What proves this works?" | Read the Evidence column, then open the referenced bundle or CI artifact. |
| "Can we claim capability X?" | Check the capability matrix status and the bundle level (A2 vs A3/A4). |
| "What breaks if we delay item Y?" | Check §6; if Y is on the critical path, the release slips one-for-one. |
| "Is requirement Z covered?" | Every requirement in §2–§5 has at least one test layer and one evidence type; an empty cell is a defect. |
| "Which epic owns this?" | §7 maps epics to requirements bidirectionally. |

## 11. Change log discipline

Each modification to this table records, in the PR description: the requirement ids touched, whether coverage increased or decreased, and the evidence artifact that justifies any new `pass` claim. Coverage may never decrease silently — a removed test mapping requires either a replacement mapping or an explicit governance-approved risk acceptance added to §9.
