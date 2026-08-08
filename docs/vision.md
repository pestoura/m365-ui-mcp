# Planner MCP — Canonical Product Vision

Planner MCP is a production-grade semantic Model Context Protocol (MCP) server for
Microsoft Planner Premium. It enables agents and tooling to operate Planner Premium
through a stable, intent-level interface rather than brittle UI scripting.

## Primary execution path

The primary execution path is a private Playwright/Chromium browser worker. All
Planner Premium operations are performed through a controlled, persistent browser
session owned and operated by the server.

Microsoft Graph availability is **not** a functional gate. The system must remain
operable and degrade safely when Graph is unavailable; the browser worker is the
authoritative execution substrate, not a fallback.

## Public MCP surface

Public MCP tools are **semantic**, never raw click/type primitives. Tools expose
intent (e.g. `create_plan`, `assign_task`, `move_task_to_bucket`, `sync_state`),
not low-level UI actions. The browser automation layer is an internal implementation
detail and is never exposed directly through the MCP contract.

## Safety and trust

The server **fails closed** on any unverified UI state. If the browser worker cannot
confirm the resulting interface state, the operation is rejected and reported as
unverified rather than partially applied or silently assumed successful.

## Privacy and access boundaries

- **Personal-device privacy boundary:** the browser worker is bound to the operator's
  professional profile and must never reach into, observe, or persist personal-device
  data outside the configured professional scope.
- **Conditional Access blocker:** enterprise Conditional Access policies are treated
  as hard gates. If access is blocked or challenged in a way the worker cannot lawfully
  and safely satisfy, execution stops rather than attempting to bypass controls.

## Session and identity

- A **persistent professional browser profile** is maintained so authenticated sessions,
  cookies, and Planner Premium context survive restarts and reconcile deterministically.
- MFA is satisfied exclusively via **Microsoft Authenticator approval only**; no other
  approval path is accepted or attempted.

## Architecture

- **Control-plane / browser-worker separation:** the MCP control plane (tool contract,
  validation, reconciliation, observability) is decoupled from the browser worker
  (UI execution). The control plane orchestrates; the worker executes and reports
  verified outcomes.
- **Desired-state reconciliation:** the server continuously reconciles actual Planner
  Premium state against the desired state expressed through the semantic tools,
  resolving drift without destructive re-application.

## Production posture

Security, observability, and CI are **first-class requirements**, not afterthoughts:

- least-privilege execution and credential isolation by default
- auditable, redacted, structured logs and metrics
- automated CI gates for build, lint, tests, and security before any release

This vision is canonical. Implementation decisions must be measured against it; where
the document and code diverge, the divergence is a tracked issue, not silent drift.
