# Vision

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

## Product statement

Planner MCP is a **governed semantic control plane** for Planner Premium. It exposes
project-management intent (`planner_task_list`, later `planner_dependency_set`) rather than
mechanics (`click`, `type`). It executes intent through a private browser worker that owns an
isolated authenticated session, and it treats the **UI as the contract and the evidence**.

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

## Users

- **Agent operator (ChatGPT / MCP client)** — asks for project state and, later, project change.
- **Human owner (Pedro)** — owns credentials, approves MFA, approves `REQUIRE_APPROVAL` operations.
- **Reviewer/auditor** — reads structured logs, attestation records and reconciliation reports.

## Explicit non-goals

- Not a Graph wrapper, not a Planner clone, not a data warehouse.
- Not a credential vault and not an MFA transport.
- Not a general browser automation service; no public raw input primitives, ever.
- Not a device management or compliance tool.

## Success criteria (A1 scope)

The specification is complete when every capability, tool, state and control described here has a
stable requirement ID in [traceability.md](traceability.md), a decision record where the choice is
contested, and a Definition of Done that later code and tests can be measured against.
