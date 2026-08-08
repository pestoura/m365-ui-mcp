# Architecture

```
ChatGPT
  -> Cloudflare MCP Server Portal
    -> planner-mcp control plane (FastMCP, Streamable HTTP)
      -> planner-browser-worker (FastAPI, private network only)
        -> Playwright / Chromium persistent professional profile
          -> Microsoft Planner Premium web UI
```

Hermes is **not** the browser execution layer. It stays outside this path and is used only for
notifications and human-in-the-loop orchestration.

## Separation of concerns
| Component | Responsibility | Never does |
| --- | --- | --- |
| Control plane | MCP tools, policy, state, contracts, metrics | Drive a browser |
| Browser worker | Playwright/Chromium session, UI reads | Expose a public port, store secrets in state |

## Packages
- `planner_mcp` — control plane: config, policy, state, contracts, capabilities, tools, metrics.
- `planner_mcp.{approvals,checkpoints,sagas,locks,reconciliation,reporting,notifications}` — architecture skeletons.
- `planner_mcp.planner.{plans,tasks,buckets,dependencies,scheduling,goals,sprints,resources,fields,portfolios}` — domain skeletons.
- `planner_browser_worker` — FastAPI app, persistent browser abstraction, auth/MFA detection, mock data.

## Design principles
Desired-state and reconciliation first; stable `external_id`/`source_id`; idempotency with read-back
before retry; typed resource locks; sagas with checkpoints; fail-closed policy; structured redacted
logs; low-cardinality metrics.
