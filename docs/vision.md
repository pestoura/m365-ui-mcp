# Vision

> **Document status:** Normative, specification-foundation.
> **Version:** 0.1.0 (A1 scope). **Owner:** Maintainer (architecture + ADRs).
> **Companion docs:** [architecture.md](architecture.md), [privacy-boundary.md](privacy-boundary.md),
> [threat-model.md](threat-model.md), [idempotency.md](idempotency.md),
> [planner-premium-capabilities.md](planner-premium-capabilities.md), [governance.md](governance.md),
> [traceability.md](traceability.md).
> This file states *why the product exists and what it refuses to become*. Every later normative
> claim (a principle, a non-goal, a success criterion) must be traceable here or in an ADR.

## Executive summary

`planner-mcp` is a production-grade Model Context Protocol (MCP) server that lets an AI agent
operate **Microsoft Planner Premium** (the Project-for-the-web lineage: WBS, dependencies,
scheduling, goals, sprints, people/workload, portfolios) **safely, observably and governed** —
and does so **primarily through a private, human-owned browser session**, not through the public
Graph API surface. The product is deliberately narrow: it is a *control plane* that turns
project-management **intent** into verified **state change**, and treats the Planner UI itself as
both the contract it obeys and the evidence it keeps.

The product exists because the public API surface is narrower than the product, tenant licensing
and Conditional Access make capability *environment-specific*, and naive automation (raw
click/type/navigate exposed as tools) is unsafe, non-idempotent and impossible to govern. We close
that gap without compromising the human's ownership of identity or the personal device's privacy.

## Problem

Microsoft Planner Premium (Project for the web lineage) is where real project structure lives:
WBS, dependencies, scheduling, goals, sprints, people/workload, portfolios. Agents cannot
operate it reliably today because:

1. The public API surface (Graph) is narrower than the product. Premium project semantics
   are partially or entirely absent from documented endpoints.
2. Tenant licensing, Conditional Access and feature flags make capability **environment-specific**.
   What is documented is not what is available.
3. Naive automation (raw click/type/navigate exposed as tools) is unsafe, non-idempotent and
   impossible to govern or audit.

Each of these is a *structural* problem, not a missing endpoint. Solving (1) by scraping harder
without solving (2) and (3) produces automation that silently does the wrong thing in a tenant it
does not understand, with no audit trail and no way back.

## Product statement

Planner MCP is a **governed semantic control plane** for Planner Premium. It exposes
project-management intent (`planner_task_list`, later `planner_dependency_set`) rather than
mechanics (`click`, `type`). It executes intent through a private browser worker that owns an
isolated authenticated session, and it treats the **UI as the contract and the evidence**.

The control plane is the only place that understands *meaning* — tool semantics, policy, desired
state, idempotency, reconciliation and observability. The browser worker is the only place that
touches the UI, and it is never publicly reachable and never exposes raw input primitives. The
human owns identity end-to-end. Hermes (or any out-of-band agent) can notify and carry sanitized
human-in-the-loop payloads, but can never approve MFA, never transport a secret, and never invoke
a mutation. See [architecture.md](architecture.md#1-canonical-topology) for the topology and
[ADR-002](adr/ADR-002-control-plane-worker-separation.md) for the rationale.

## Principles

- **P1 Evidence over documentation.** A capability is supported when observed and attested,
  never because a doc or endpoint exists. ([ADR-006](adr/ADR-006-graph-not-a-functional-gate.md))
- **P2 Semantics over mechanics.** Only meaningful project operations are exposed.
  ([ADR-001](adr/ADR-001-browser-automation.md), [tool-catalog](tool-catalog.md))
- **P3 Reconcile, do not fire-and-forget.** Every mutation is expressed as desired state and
  verified by read-back. ([ADR-003](adr/ADR-003-reconciliation-first.md))
- **P4 Fail closed.** Ambiguity is a stop condition, not a reason to guess. ([security](security.md))
- **P5 The human owns identity.** Password and MFA approval never leave the human and the
  Authenticator app. ([ADR-004](adr/ADR-004-human-in-loop-mfa.md))
- **P6 The personal device stays personal.** No enrolment, no management, no corporate agents.
  ([ADR-008](adr/ADR-008-personal-device-privacy-boundary.md))
- **P7 Small, attested surface.** 0.1.0 ships read-only tools only. Mutation is earned by evidence.

### Principle → specification traceability

| Principle | Normative home | Key requirement IDs |
| --- | --- | --- |
| P1 Evidence over documentation | [planner-premium-capabilities.md](planner-premium-capabilities.md), [governance.md](governance.md#attestation-governance) | SEC-007, AC-1 |
| P2 Semantics over mechanics | [tool-catalog.md](tool-catalog.md), [ADR-001](adr/ADR-001-browser-automation.md) | T3, T15 |
| P3 Reconcile, do not fire-and-forget | [reconciliation.md](reconciliation.md), [idempotency.md](idempotency.md) | SEC-065, T6 |
| P4 Fail closed | [security.md](security.md#7-fail-closed-invariants) | SEC-060..SEC-067 |
| P5 The human owns identity | [authentication-and-mfa.md](authentication-and-mfa.md), [ADR-004](adr/ADR-004-human-in-loop-mfa.md) | SEC-002, T8, T9 |
| P6 The personal device stays personal | [privacy-boundary.md](privacy-boundary.md), [ADR-008](adr/ADR-008-personal-device-privacy-boundary.md) | SEC-003, SEC-040 |
| P7 Small, attested surface | [roadmap.md](roadmap.md), [tool-catalog.md](tool-catalog.md) | capability-state transitions |

## Users

- **Agent operator (ChatGPT / MCP client)** — asks for project state and, later, project change.
  Never an approver of MFA; never a policy authority.
- **Human owner (Pedro)** — owns credentials, approves MFA, approves `REQUIRE_APPROVAL` operations.
- **Reviewer/auditor** — reads structured logs, attestation records and reconciliation reports.

A fourth, implicit stakeholder is the **tenant administrator**, whom the product must never
antagonise: when Conditional Access requires a managed device, the correct output is a clean
`BLOCKER_CONDITIONAL_ACCESS`, not a bypass attempt.

## Explicit non-goals

- Not a Graph wrapper, not a Planner clone, not a data warehouse.
- Not a credential vault and not an MFA transport.
- Not a general browser automation service; no public raw input primitives, ever.
- Not a device management or compliance tool.
- Not a replacement for Microsoft's own auth, audit or compliance controls — it defers to them.
- Not a tool that asserts tenant or license facts it has not directly observed.

These non-goals are load-bearing. Each one corresponds to a fail-closed behaviour and, in most
cases, to an absolute prohibition in [privacy-boundary.md](privacy-boundary.md) or a threat
mitigation in [threat-model.md](threat-model.md). A feature request that touches a non-goal is a
signal to write an ADR, not to ship a workaround.

## Scope model (A1 and beyond)

The product grows by **evidence**, not by roadmap ambition. The surface widens only as capabilities
move through the support-level ladder (`UNVERIFIED_LIVE → DISCOVERED → UI_ATTESTED → READ_ATTESTED →
MUTATION_ATTESTED → SUPPORTED`). See
[planner-premium-capabilities.md](planner-premium-capabilities.md#capability-states).

| Release | Surface | Mutation? | Entry bar |
| --- | --- | --- | --- |
| **0.1.0 (A1)** | Read-only semantic tools (`planner_task_list`, project/detail reads, readiness, auth status) | No | Read attestation only; every row `UNVERIFIED_LIVE` until observed |
| **0.2.0** | Additive safe writes (buckets, subtasks, assignments) | Yes, `SAFE_WRITE`/`GOVERNED_WRITE` | `MUTATION_ATTESTED` + read-back + approval path |
| **0.3.0+** | Semantic mutations (dependencies, scheduling, portfolios) and reconciliation sagas | Yes, `DESTRUCTIVE` where needed | Full attestation + compensation plans + policy |
| **Future** | Possibly Graph-backed read where parity is provable | Mixed | Only if P1 is preserved (evidence still authoritative) |

A1 explicitly ships **read-only** so that the entire governance, evidence, privacy and
fail-closed machinery is exercised and trusted before any tenant state is changed. Mutation is
"earned by evidence" (P7): no capability may be `SUPPORTED` for writes until a successful
apply **and** read-back has been demonstrated against the mock UI and, later, the live tenant.

## Privacy and trust posture (summary)

Three trust facts are non-negotiable and are expanded normatively elsewhere:

1. **The password never exists in any artefact this system controls** — entered by the human, in
   the browser, into Microsoft's own page. (SEC-001, SEC-020.)
2. **The device is never enrolled or managed** — no Intune, no broker, no MDM, no device
   certificate. (SEC-003, SEC-040, [privacy-boundary.md](privacy-boundary.md).)
3. **Tenant data leaves its trust zone only as sanitized output** — raw DOM, screenshots and
   identifiers never reach the MCP client, Hermes or logs in raw form. (SEC-006, SEC-070.)

The trust model is *out of band by construction*: Hermes can notify and carry sanitized HITL
payloads but cannot approve MFA, transport a secret, or invoke a mutation (SEC-013, T8).

## Determinism and evidence-first operation

"Evidence over documentation" (P1) is operationalised as:

- A capability's `support_level` is **computed from the attestation ledger**, never authored by
  hand. Rows without evidence stay `UNVERIFIED_LIVE`.
- `Graph` is treated as *contextual information only* and is **never a functional gate**
  ([ADR-006](adr/ADR-006-graph-not-a-functional-gate.md)).
- Any tool whose capability is below `READ_ATTESTED` cannot be `ALLOW`ed for reads; mutations
  require `MUTATION_ATTESTED` (SEC-051).
- Read-back is mandatory: `READ_BACK_OK` is the only success terminal for a mutation
  (state-model operation transitions). There is no "fire and forget."

## Operating constraints

- **Personal device.** The host running `planner-mcp` is a personal machine and must remain so.
  See [privacy-boundary.md](privacy-boundary.md).
- **Human-in-the-loop.** Password entry and MFA approval happen only with the human, in Microsoft
  Authenticator. See [authentication-and-mfa.md](authentication-and-mfa.md) and
  [ADR-004](adr/ADR-004-human-in-loop-mfa.md).
- **Fail closed.** Ambiguity stops the pipeline. See [security.md](security.md#7-fail-closed-invariants).
- **Private by default.** The worker is on an internal-only network with no public ingress; the
  control plane binds loopback; public exposure exists only through the Cloudflare Portal
  (SEC-010, SEC-011).

## Success metrics (A1)

Success is observable, not aspirational:

- **Completeness:** every capability, tool, state and control has a stable requirement ID in
  [traceability.md](traceability.md), a decision record where the choice is contested, and a
  Definition of Done that later code and tests can be measured against.
- **Evidence integrity:** no `SUPPORTED` capability exists without an attestation record and a
  linked evidence handle; the attestation ledger is append-only and auditable.
- **Fail-closed coverage:** every `SEC-060..067` invariant has a corresponding unit/mock-UI test
  that proves the refusals fire.
- **Privacy proof:** CI asserts the repository contains no enrolment automation, no secret, and no
  selector written into a capability doc (`scripts/check_no_secrets.sh`,
  `scripts/assert_no_live_tenant.py`).
- **No live-tenant dependency:** CI never authenticates to a live tenant; acceptance runs against
  the mock UI only.

## Relationship to the rest of the specification

| Topic | Document |
| --- | --- |
| Topology, planes, request lifecycle, trust zones | [architecture.md](architecture.md) |
| Personal-device prohibitions and isolation | [privacy-boundary.md](privacy-boundary.md) |
| STRIDE, assets, abuse cases, residual risk | [threat-model.md](threat-model.md) |
| Idempotency, fingerprint, read-back, circuit breakers | [idempotency.md](idempotency.md) |
| Capability ladder and matrix | [planner-premium-capabilities.md](planner-premium-capabilities.md) |
| Policy, mutation classes, approvals, blockers | [governance.md](governance.md) |
| Auth state machine and MFA boundary | [authentication-and-mfa.md](authentication-and-mfa.md) |
| UI as contract, selector attestation | [ui-contract.md](ui-contract.md) |
| Requirement IDs and coverage | [traceability.md](traceability.md) |
| Security objectives and controls | [security.md](security.md) |

## Open questions and risks for A1

- **Premium reachability.** If the live tenant's Premium surface is unreachable due to licensing
  or Conditional Access, A1 still succeeds as a *specification* — the matrix records
  `BLOCKED_CONDITIONAL_ACCESS` / `UNSUPPORTED_TENANT` rather than asserting capability.
- **UI drift velocity.** Premium UI changes may outpace attestation; the drift-detection and
  fail-closed path (SEC-060, `UI_DRIFT`) is the safety net, not a blocker to shipping.
- **Attestation burden.** Recording evidence for every selector is heavy; A1 scopes attestation
  to the read paths actually exercised and leaves write attestation for 0.2.0+.

## Glossary

- **Control plane** — the `planner-mcp` process: tools, policy, desired/observed state,
  idempotency, reconciliation, observability. Never owns a browser or a password.
- **Browser worker** — `planner-browser-worker`: owns the Chromium persistent profile and the
  live authenticated session; drives the UI under UIContract; never publicly reachable.
- **Support level** — a capability's position on the evidence ladder
  (`UNVERIFIED_LIVE … SUPPORTED`); computed, never asserted.
- **Evidence / attestation** — a captured, hash-referenced observation (selector, read result, or
  apply+read-back) recorded in the attestation ledger.
- **Blocker** — a typed, terminal stop condition (`BLOCKER_CONDITIONAL_ACCESS`,
  `BLOCKER_UI_DRIFT`, `BLOCKER_POLICY_UNCERTAIN`, `BLOCKER_AMBIGUOUS_SESSION`,
  `BLOCKER_LICENSE_UNVERIFIED`, `BLOCKER_EVIDENCE_MISSING`) returned verbatim to the caller.
- **Read-back** — re-reading the affected entity from the UI after a mutation; required before any
  success is reported.

## Success criteria (A1 scope)

The specification is complete when every capability, tool, state and control described here has a
stable requirement ID in [traceability.md](traceability.md), a decision record where the choice is
contested, and a Definition of Done that later code and tests can be measured against.
