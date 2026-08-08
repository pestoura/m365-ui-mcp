# Vision

planner-mcp is a production-oriented MCP server that lets an agent operate Microsoft Planner Premium
through a **private Chromium/Playwright browser worker**, not through Microsoft Graph.

Graph availability is explicitly **not** a functional gate. Where Graph does not expose a Planner
Premium capability, the browser path remains the primary and authoritative execution channel.

## Outcomes
- A read-only, evidence-driven Foundation (0.1.0) with a hard no-mutation guarantee.
- A capability model built from tenant/license/UI/UIContract/runtime evidence.
- A path to safe, reversible, approval-gated mutations in later releases.

## Non-goals for 0.1.0
- No mutations of any kind.
- No Microsoft Graph backend.
- No device enrolment, MDM, Intune, Company Portal or Conditional Access bypass.
