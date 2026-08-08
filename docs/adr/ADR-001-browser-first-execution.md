# Browser-first execution instead of Microsoft Graph

- Status: Accepted
- Date: 2026-08-08

## Context
Planner Premium capabilities are incompletely exposed by Graph, and Graph availability must not gate product scope.

## Decision
Use a private Playwright/Chromium worker driving the Planner Premium web UI as the primary execution path. Graph is not used as a backend.

## Consequences
Higher fragility against UI change, mitigated by a versioned UIContract with attestation and drift detection.
