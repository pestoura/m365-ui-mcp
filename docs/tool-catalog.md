# Tool catalog

Contract version **0.1.0**. Public MCP tools are **semantic project operations**. Raw browser
navigation (`click`, `type`, `goto`) is never exposed (ADR-001, SEC-020).

## Manifest metadata

Every tool declares:

| Field | Values |
| --- | --- |
| `trust_level` | `INTROSPECTION`, `TENANT_READ`, `TENANT_WRITE`, `PRIVILEGED` |
| `mutation_class` | `READ`, `SAFE_WRITE`, `GOVERNED_WRITE`, `DESTRUCTIVE` |
| `reversible` | `true`, `false`, `n/a` |
| `idempotency_class` | `PURE_READ`, `NATURAL_IDEMPOTENT`, `KEYED_IDEMPOTENT`, `NON_IDEMPOTENT` |
| `approval_requirement` | `NONE`, `POLICY_CONDITIONAL`, `ALWAYS` |
| `attestation_status` | `UNVERIFIED_LIVE`, `UI_ATTESTED`, `READ_ATTESTED`, `MUTATION_ATTESTED`, `SUPPORTED` |

### Manifest kinds

- **CapabilityManifest** — what the server can do in this tenant *right now*: capability rows,
  states, UI contract version, blockers. Derived from the capability matrix plus runtime probes.
- **AgentCard** — identity and operating envelope of the server: name, version, protocol,
  supported mutation classes, human-in-loop requirements, privacy boundary statement, contact.
- **ToolManifest** — the MCP-visible tool list: name, description, input/output schema.
- **ExtendedToolManifest** — ToolManifest plus the governance metadata above, policy rule id,
  required locks, read-back strategy and drift behaviour. Used by the policy engine and by
  clients that need to reason about risk before calling.

Schemas: [`docs/schemas/`](schemas/).

## 0.1.0 — read-only surface

| Tool | Purpose | trust | mutation | idempotency | approval | attestation |
| --- | --- | --- | --- | --- | --- | --- |
| `planner_health` | Liveness of control plane; no tenant contact. | INTROSPECTION | READ | PURE_READ | NONE | SUPPORTED |
| `planner_readiness` | Readiness: worker reachable, profile present, contract loaded, auth state. | INTROSPECTION | READ | PURE_READ | NONE | SUPPORTED |
| `planner_capabilities` | Current CapabilityManifest. | INTROSPECTION | READ | PURE_READ | NONE | SUPPORTED |
| `planner_agent_card` | AgentCard. | INTROSPECTION | READ | PURE_READ | NONE | SUPPORTED |
| `planner_ui_contract_status` | Contract version, fragment attestation states, drift findings. | INTROSPECTION | READ | PURE_READ | NONE | SUPPORTED |
| `planner_auth_status` | Current formal auth state. Never blocks. | TENANT_READ | READ | PURE_READ | NONE | UNVERIFIED_LIVE |
| `planner_auth_start` | Open interactive sign-in in the persistent profile. Enters no credentials. | TENANT_READ | READ | NATURAL_IDEMPOTENT | NONE | UNVERIFIED_LIVE |
| `planner_auth_resume` | Re-probe after human action (e.g. MFA approved). | TENANT_READ | READ | NATURAL_IDEMPOTENT | NONE | UNVERIFIED_LIVE |
| `planner_auth_session_info` | Non-secret session facts (state, expiry hint, profile id). | TENANT_READ | READ | PURE_READ | NONE | UNVERIFIED_LIVE |
| `planner_plan_list` | List plans/projects visible to the session. | TENANT_READ | READ | PURE_READ | NONE | UNVERIFIED_LIVE |
| `planner_plan_get` | Read one plan by `external_id`. | TENANT_READ | READ | PURE_READ | NONE | UNVERIFIED_LIVE |
| `planner_task_list` | List tasks of a plan with typed fields. | TENANT_READ | READ | PURE_READ | NONE | UNVERIFIED_LIVE |
| `planner_task_get` | Read one task by `external_id`. | TENANT_READ | READ | PURE_READ | NONE | UNVERIFIED_LIVE |
| `planner_project_snapshot` | Consistent composite read: plan + buckets + tasks + edges, with snapshot hash. | TENANT_READ | READ | PURE_READ | NONE | UNVERIFIED_LIVE |
| `planner_account_context` | Observed account context label and tenant reachability; no UPN unless unambiguous and permitted. | TENANT_READ | READ | PURE_READ | NONE | UNVERIFIED_LIVE |
| `planner_license_capabilities` | Premium capabilities *observed* in the UI; never inferred from Graph or marketing. | TENANT_READ | READ | PURE_READ | NONE | UNVERIFIED_LIVE |
| `planner_smoke_test` | Bounded read-only end-to-end check; returns typed findings. | TENANT_READ | READ | PURE_READ | NONE | UNVERIFIED_LIVE |

All 0.1.0 tools return `contract_version`, `operation_id`, and where UI-derived
`ui_contract_version` + `evidence_hash`. Any read that touches an unattested fragment fails
closed rather than returning a partial guess.

## Future catalog (semantic, by domain)

Names are reserved; none are implemented in 0.1.0.

**Plans / projects** — `planner_plan_create`, `planner_plan_update`, `planner_plan_archive`,
`planner_plan_delete`, `planner_plan_duplicate`.

**Tasks / WBS** — `planner_task_create`, `planner_task_update`, `planner_task_move`,
`planner_task_delete`, `planner_wbs_get`, `planner_wbs_apply`, `planner_subtask_add`,
`planner_checklist_set`.

**Buckets** — `planner_bucket_list`, `planner_bucket_create`, `planner_bucket_rename`,
`planner_bucket_reorder`, `planner_bucket_delete`.

**Dependencies** — `planner_dependency_list`, `planner_dependency_add`,
`planner_dependency_remove`, `planner_dependency_validate` (cycle/lag checking before apply).

**Scheduling** — `planner_schedule_get`, `planner_schedule_set`, `planner_milestone_set`,
`planner_effort_set`, `planner_critical_path_get`, `planner_calendar_get`,
`planner_calendar_set`.

**Goals** — `planner_goal_list`, `planner_goal_link`, `planner_goal_unlink`.

**Sprints** — `planner_sprint_list`, `planner_sprint_create`, `planner_sprint_assign`,
`planner_backlog_get`.

**Resources / people** — `planner_people_list`, `planner_workload_get`, `planner_assign`,
`planner_unassign`, `planner_resource_rebalance`.

**Custom fields** — `planner_custom_field_list`, `planner_custom_field_define`,
`planner_custom_field_set`, `planner_formatting_rules_get`, `planner_formatting_rules_set`.

**Portfolios** — `planner_portfolio_list`, `planner_portfolio_get`, `planner_portfolio_add_plan`,
`planner_roadmap_get`.

**Reporting** — `planner_report_status`, `planner_report_variance`, `planner_report_export`.

**Reconciliation / blueprints** — `planner_blueprint_validate`, `planner_blueprint_plan`
(dry-run diff), `planner_blueprint_apply`, `planner_reconcile_status`,
`planner_reconcile_resume`, `planner_import_dry_run`.

**Governance** — `planner_policy_explain`, `planner_approval_request`, `planner_approval_status`,
`planner_operation_status`, `planner_lock_status`, `planner_drift_report`.

## Naming rules

`planner_<domain>_<verb>`; verbs are project verbs (`list`, `get`, `create`, `assign`,
`reconcile`), never UI verbs. Every mutating tool must name its read-back strategy in the
ExtendedToolManifest before implementation.
