# Tool catalog (0.1.0) — 17 read-only tools

Every tool is read-only, `mutation_class=none`, `reversible=true`, `idempotency_class=pure_read`.

| # | Tool | Category | Purpose |
| --- | --- | --- | --- |
| 1 | planner_health | system | Control-plane liveness and versions |
| 2 | planner_readiness | system | SQLite + worker + UIContract readiness |
| 3 | planner_capabilities | capability | Evidence-based capability matrix |
| 4 | planner_agent_card | system | AgentCard, ToolManifest, ExtendedToolManifest |
| 5 | planner_ui_contract_status | ui_contract | UIContract version and attestation |
| 6 | planner_auth_status | auth | Current auth state |
| 7 | planner_auth_start | auth | Start an interactive auth attempt |
| 8 | planner_auth_resume | auth | Poll/resume, surfacing sanitized MFA metadata |
| 9 | planner_auth_session_info | auth | Sanitized persistent-profile session info |
| 10 | planner_plan_list | planner_read | List plans |
| 11 | planner_plan_get | planner_read | Read one plan |
| 12 | planner_task_list | planner_read | List tasks of a plan |
| 13 | planner_task_get | planner_read | Read one task |
| 14 | planner_project_snapshot | planner_read | Composite plan snapshot |
| 15 | planner_account_context | auth | Sanitized account/tenant context |
| 16 | planner_license_capabilities | capability | License evidence |
| 17 | planner_smoke_test | system | Isolated read-only smoke test |

Extended metadata per tool: `trust_level`, `mutation_class`, `reversible`, `idempotency_class`,
`approval_requirement`, `attestation_status` (see `contracts/extended_tool_manifest.json`).
