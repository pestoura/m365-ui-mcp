# planner-mcp

Production-oriented **MCP server for Microsoft Planner Premium**, driven by a private
Chromium/Playwright browser worker. **Microsoft Graph is not used as a backend.**

```
ChatGPT -> Cloudflare MCP Server Portal -> planner-mcp control plane -> planner-browser-worker -> Playwright/Chromium -> Planner Premium
```

Hermes is not the browser execution layer; it handles notifications and HITL orchestration only.

## Status: Foundation 0.1.0 — read-only

- 17 read-only MCP tools, zero mutations (policy-denied and test-enforced).
- Product / schema / contract versions: `0.1.0`.
- UIContract is **unattested** (`UNVERIFIED_LIVE`): live mode fails closed with
  `UI_CONTRACT_UNATTESTED`. Selectors are never fabricated.
- Conditional Access demanding a managed device => `BLOCKER_CONDITIONAL_ACCESS`. No enrolment, ever.
- MFA number matching is only *detected*; approval happens exclusively in Microsoft Authenticator.

## Tools

`planner_health`, `planner_readiness`, `planner_capabilities`, `planner_agent_card`,
`planner_ui_contract_status`, `planner_auth_status`, `planner_auth_start`, `planner_auth_resume`,
`planner_auth_session_info`, `planner_plan_list`, `planner_plan_get`, `planner_task_list`,
`planner_task_get`, `planner_project_snapshot`, `planner_account_context`,
`planner_license_capabilities`, `planner_smoke_test`.

## Quick start (development, mock mode)

```bash
python3.12 -m venv .venv && . .venv/bin/activate
pip install -e ".[dev]"
ruff check . && mypy && pytest
python scripts/isolated_acceptance.py
```

## Deployment

```bash
docker compose up -d --build
```

The worker has no published port and lives on an internal network. Healthchecks use
`planner-mcp-healthcheck` (SQLite + control-plane TCP + worker `/health`), never `GET /mcp`.

## Documentation

`docs/vision.md`, `architecture.md`, `threat-model.md`, `security.md`, `governance.md`,
`authentication-and-mfa.md`, `privacy-boundary.md`, `planner-premium-capabilities.md`,
`tool-catalog.md`, `reconciliation.md`, `idempotency.md`, `state-model.md`, `ui-contract.md`,
`browser-worker.md`, `observability.md`, `testing.md`, `acceptance.md`, `deployment.md`,
`cloudflare-mcp-portal.md`, `hermes-integration.md`, `reporting.md`, `roadmap.md`, `backlog.md`
and `docs/adr/ADR-001..005`.

## Verified controls

Base images are pinned by digest and enforced by a blocking CI gate. Both images build locally and
in CI; Trivy CRITICAL/HIGH gates and CycloneDX SBOMs run against both.
