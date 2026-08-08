# Planner MCP — Tool Catalog

Status: specification (implementation-grade). Every tool below is a *contract*, not a claim of
implementation; unimplemented tools are `PLANNED` (`GOV-090`).
Canonical upstream: [docs/vision.md](./vision.md)
Related: [docs/architecture.md](./architecture.md) · [docs/security.md](./security.md) · [docs/privacy-boundary.md](./privacy-boundary.md) · [docs/governance.md](./governance.md) · [docs/ui-contract.md](./ui-contract.md) · [docs/browser-worker.md](./browser-worker.md) · [docs/planner-premium-capabilities.md](./planner-premium-capabilities.md) · [docs/authentication-and-mfa.md](./authentication-and-mfa.md)

Requirement IDs (`TOOL-xxx`) are stable, never reused, never renumbered.

---

## 1. Surface rules

**TOOL-001 — The public MCP surface is semantic only.** Tools express domain intent. UI mechanics
are internal (`ARCH-020`, `ARCH-021`).

**TOOL-002 — Closed catalog.** Only tools in this catalog are registered. Unknown tool names are
denied by identity, not by pattern (`SEC-011`).

**TOOL-003 — Every tool declares exactly one mutation class.** Absence is denial, not `READ`
(`SEC-020`, `SEC-021`).

**TOOL-004 — The 0.1.0 catalog is read-only.** Every published tool is `READ`; the policy engine
denies every non-read tool (`SEC-007`).

**TOOL-005 — Forbidden forever on the public surface:** `browser_click`, `browser_type`,
`browser_exec`, `browser_navigate`, `browser_evaluate`, `browser_screenshot`, any tool accepting or
returning CSS/XPath selectors, raw DOM, cookies, storage state or page URLs (`SEC-005`, `UI-004`).

**TOOL-006 — No escape hatch.** A generic execution tool requires an ADR and is rejected by default
(`ARCH-022`).

**TOOL-007 — Tool contracts are versioned.** Breaking argument or result changes require a new
version, not a silent change (`GOV-023`, `GOV-063`).

---

## 2. Manifest metadata

**TOOL-010 — `ToolManifest`** (the base contract published with each tool):

| Field | Meaning |
| --- | --- |
| `name` | Canonical tool name; stable and unique |
| `version` | Tool contract semantic version |
| `catalog_version` | Version of the catalog this tool belongs to |
| `summary` | Short semantic description; no UI mechanics |
| `inputs` | Typed argument schema; no selectors, no URLs, no credentials |
| `outputs` | Typed result schema; sanitized by construction |
| `mutation_class` | `READ` \| `SAFE_WRITE` \| `GOVERNED_WRITE` \| `DESTRUCTIVE` |
| `capability_keys` | The `CAP-xxx` rows this tool depends on |

**TOOL-011 — `ExtendedToolManifest`** adds the trust and governance metadata:

| Field | Values | Meaning |
| --- | --- | --- |
| `trust_level` | `untrusted_ui_derived` \| `system_derived` | Provenance of the returned data |
| `mutation_class` | as above | Restated authoritatively for policy input |
| `reversible` | `yes` \| `with_compensation` \| `no` | Whether the effect can be undone |
| `idempotency_class` | `naturally_idempotent` \| `key_required` \| `non_idempotent` | Retry eligibility (`ARCH-093`) |
| `approval_requirement` | `none` \| `configurable` \| `always` | HITL posture (`SEC-010`) |
| `attestation_status` | `UNVERIFIED_LIVE` \| `DISCOVERED` \| `UI_ATTESTED` \| `READ_ATTESTED` \| `MUTATION_ATTESTED` \| `SUPPORTED` \| `UI_DRIFT` | Aggregated from the tool's capability keys (`UI-041`) |

**TOOL-012 — The manifest is policy input, not documentation.** The policy engine reads these
fields; a tool whose manifest fails schema validation is not registered.

**TOOL-013 — `attestation_status` is derived, never hand-set.** It is the minimum of the states of
the capability keys the tool depends on.

**TOOL-014 — Manifests are exposed read-only** through `planner_capabilities` and
`planner_agent_card`, without any locator or identity material.

---

## 3. Catalog 0.1.0 — canonical read-only tools

**TOOL-020 — The 0.1.0 catalog contains exactly these seventeen names**, no more and no fewer:

`planner_health`, `planner_readiness`, `planner_capabilities`, `planner_agent_card`,
`planner_ui_contract_status`, `planner_auth_status`, `planner_auth_start`, `planner_auth_resume`,
`planner_auth_session_info`, `planner_plan_list`, `planner_plan_get`, `planner_task_list`,
`planner_task_get`, `planner_project_snapshot`, `planner_account_context`,
`planner_license_capabilities`, `planner_smoke_test`.

**TOOL-021 — All seventeen are `mutation_class: READ`.** The authentication tools change no Planner
state: they open or observe an interactive human sign-in and are classified `READ` with
`idempotency_class: naturally_idempotent` for `planner_auth_resume` and `key_required` for
`planner_auth_start` (the `operation_id` is the key, `AUTH-055`).

### 3.1 Platform tools

**TOOL-030 `planner_health`**
Purpose: liveness of the control plane. Inputs: none. Outputs: `status`, `version`.
Preconditions: none. Policy: `ALLOW`. Auth/UI: none required.
Errors: none expected; failure is transport-level. Evidence: none.

**TOOL-031 `planner_readiness`**
Purpose: readiness of the whole system. Inputs: none. Outputs: `ready`, `mode` (`mock`/`live`),
`contract_version`, `worker_ready`, `auth_state`, `mutations_enabled` (always `false` in 0.1.0).
Preconditions: none. Policy: `ALLOW`. Auth/UI: reports state, does not require it.
Errors: `WORKER_UNAVAILABLE` reported as a field, not an exception. Evidence: readiness snapshot.

**TOOL-032 `planner_capabilities`**
Purpose: the sanitized capability matrix as data. Inputs: optional `capability_key` filter.
Outputs: rows with `capability_key`, `support_state`, `attestation_status`, `read_validated`,
`mutation_validated`. Preconditions: none. Policy: `ALLOW`. Auth/UI: none.
Errors: `CAPABILITY_UNKNOWN`. Evidence: must equal
[docs/planner-premium-capabilities.md](./planner-premium-capabilities.md) (`CAP-070`).

**TOOL-033 `planner_agent_card`**
Purpose: machine-readable description of the server, catalog version, tool manifests and posture.
Inputs: none. Outputs: server identity, `catalog_version`, tool list with
`ExtendedToolManifest` metadata, explicit statement that mutations are disabled.
Preconditions: none. Policy: `ALLOW`. Errors: none. Evidence: none.

**TOOL-034 `planner_ui_contract_status`**
Purpose: contract version and attestation posture. Inputs: optional `capability_key`.
Outputs: `contract_version`, `attested_at`, per-key `support_state` and `attestation.state`,
counts. Preconditions: contract loaded. Policy: `ALLOW`. Auth/UI: none.
Errors: `UI_DRIFT` when zones disagree (`UI-083`). Evidence: contract digest. **Never locators**
(`UI-084`).

**TOOL-035 `planner_smoke_test`**
Purpose: non-mutating end-to-end self-check of the control plane → worker → contract path.
Inputs: none. Outputs: per-stage pass/fail with sanitized reasons. Preconditions: none.
Policy: `ALLOW`. Auth/UI: does not require authentication; reports it as a stage.
Errors: `WORKER_UNAVAILABLE`, `UI_CONTRACT_UNATTESTED`, `WORKER_TIMEOUT`.
Evidence: smoke record. It performs no Planner mutation, ever.

### 3.2 Authentication tools

**TOOL-040 `planner_auth_status`**
Purpose: current authentication state. Inputs: none. Outputs: `auth_state` (one of the eight
`AUTH-020` values), `last_probe_at`, and the sanitized event fields of `AUTH-040` when an attempt is
live. Preconditions: worker ready. Policy: `ALLOW`.
Errors: `WORKER_UNAVAILABLE`. Evidence: sanitized auth audit event.

**TOOL-041 `planner_auth_start`**
Purpose: begin an interactive human sign-in in the worker's profile. Inputs: none — it accepts no
username, no password, no code, no tenant argument (`AUTH-002`, `AUTH-031`).
Outputs: `operation_id`, `auth_state`, sanitized description, `mfa_number` (nullable), `expires_at`.
Preconditions: worker ready; no other live attempt (`AUTH-055`). Policy: `ALLOW`.
Errors: `WORKER_BUSY`, `WORKER_UNAVAILABLE`, `BLOCKER_CONDITIONAL_ACCESS`.
Evidence: attempt audit record. Approval happens only in Microsoft Authenticator (`AUTH-003`).

**TOOL-042 `planner_auth_resume`**
Purpose: re-observe an in-flight attempt. Inputs: `operation_id`. Outputs: as `planner_auth_start`.
Preconditions: known, unexpired attempt. Policy: `ALLOW`. Idempotent and side-effect-free beyond
audit (`AUTH-051`). Errors: `AUTH_OPERATION_UNKNOWN`, `MFA_TIMEOUT`, `MFA_DENIED`,
`BLOCKER_CONDITIONAL_ACCESS`. Evidence: state-transition record.

**TOOL-043 `planner_auth_session_info`**
Purpose: sanitized description of the current session's validity. Inputs: none.
Outputs: `auth_state`, `session_valid`, `expires_hint` (coarse), `last_probe_at`.
Preconditions: worker ready. Policy: `ALLOW`. Errors: `SESSION_EXPIRED`, `WORKER_UNAVAILABLE`.
Evidence: probe record. Never cookies, tokens, storage state or identity (`SEC-002`).

**TOOL-044 `planner_account_context`**
Purpose: confirm which professional context the session is bound to. Inputs: none.
Outputs: opaque `account_handle`, `tenant_kind`, `context_match` boolean, `probed_at`
(`AUTH-032`). Preconditions: `AUTHENTICATED`. Policy: `ALLOW`.
Errors: `ACCOUNT_CONTEXT_MISMATCH`, `ACCOUNT_CONTEXT_AMBIGUOUS`, `AUTH_REQUIRED`.
Evidence: context probe record. Fails closed on mismatch (`AUTH-030`).

**TOOL-045 `planner_license_capabilities`**
Purpose: report *observed* licence/tenant capability signals. Inputs: none.
Outputs: per-`CAP-xxx` `tenant_license_observed` in `{UNVERIFIED_LIVE, OBSERVED, ABSENT}`.
Preconditions: `AUTHENTICATED` and verified context for anything other than `UNVERIFIED_LIVE`.
Policy: `ALLOW`. Errors: `AUTH_REQUIRED`, `UI_CONTRACT_UNATTESTED`, `WORKER_UNAVAILABLE`.
Evidence: licence-signal observation. Graph is not consulted and is irrelevant (`CAP-002`).

### 3.3 Planner read tools

**TOOL-050 `planner_plan_list`**
Purpose: list plans/projects visible to the professional context. Inputs: optional pagination and
an opaque scope hint. Outputs: array of `{external_id (opaque), name, kind, updated_hint}`, plus
`trust_level: untrusted_ui_derived`. Preconditions: `AUTHENTICATED`, context match, `CAP-100`
attested at least `UI_ATTESTED`. Policy: `ALLOW` for `READ`.
Errors: `AUTH_REQUIRED`, `ACCOUNT_CONTEXT_MISMATCH`, `UI_CONTRACT_UNATTESTED`, `UI_DRIFT`,
`WORKER_TIMEOUT`, `WORKER_UNAVAILABLE`. Evidence: read record with contract version.

**TOOL-051 `planner_plan_get`**
Purpose: read one plan's metadata. Inputs: `external_id`. Outputs: plan metadata, bucket summary
where attested, `trust_level`. Preconditions/policy/errors as `TOOL-050`, plus `PLAN_NOT_FOUND`.
Depends on `CAP-100`, and `CAP-102` when buckets are included.

**TOOL-052 `planner_task_list`**
Purpose: list tasks in a plan. Inputs: `external_id` of the plan, optional filters (bucket,
assignee handle, completion). Outputs: array of task summaries with opaque identifiers.
Preconditions: as above plus `CAP-101` attested. Errors: as above plus `PLAN_NOT_FOUND`.

**TOOL-053 `planner_task_get`**
Purpose: read one task in detail. Inputs: `external_id` of the task. Outputs: task fields,
hierarchy position, bucket, assignees (opaque handles), dates, dependency edges where attested.
Preconditions: `CAP-101`, plus `CAP-103`/`CAP-104`/`CAP-106` for the corresponding sections; an
unattested section is omitted with an explicit `omitted_sections` list, never fabricated.
Errors: as above plus `TASK_NOT_FOUND`.

**TOOL-054 `planner_project_snapshot`**
Purpose: composite, consistent-as-possible read of a plan for reconciliation input. Inputs:
`external_id`, optional section selection. Outputs: plan + tasks + buckets + attested sections,
each tagged with its own capability key and attestation state; plus `partial: true` when any
requested section was unattested or unreadable (`WORKER-083`).
Preconditions: at least `CAP-100` attested. Policy: `ALLOW`.
Errors: as above. Evidence: snapshot record with per-section provenance. A snapshot is never
presented as authoritative if `partial` is true.

---

## 4. Error classes and evidence (all tools)

**TOOL-055 — Closed error taxonomy.** `AUTH_*` (`AUTH-080`), `UI_*` ([docs/ui-contract.md](./ui-contract.md)),
`WORKER_*` ([docs/browser-worker.md](./browser-worker.md)), `POLICY_DENIED`,
`APPROVAL_REQUIRED`, `CAPABILITY_UNKNOWN`, `PLAN_NOT_FOUND`, `TASK_NOT_FOUND`, `INVALID_ARGUMENT`.

**TOOL-056 — Errors are sanitized.** Class + sanitized description + correlation id. No page text,
no stack traces, no URLs, no identity (`ARCH-112`).

**TOOL-057 — Every call emits evidence**: tool, decision, mutation class, contract version, mode,
outcome, duration. Never arguments containing tenant content in a metric label (`ARCH-111`).

---

## 5. Future semantic catalog (not published)

**TOOL-060 — Nothing below is registered until its capability row is at least `READ_SUPPORTED`**
(`CAP-071`) and, for mutations, `MUTATION_SUPPORTED` plus a governance decision (`GOV-020`).
Names are indicative; each will get its own `TOOL-xxx` contract when proposed.

| Group | Capability keys | Indicative tools | Mutation class |
| --- | --- | --- | --- |
| Plans / projects | `CAP-100` | create plan, rename plan, archive plan | `GOVERNED_WRITE`, archive `DESTRUCTIVE` |
| WBS / tasks | `CAP-101`, `CAP-105`, `CAP-106` | create task, set parent, set milestone, set duration/effort | `GOVERNED_WRITE` |
| Buckets | `CAP-102` | create bucket, rename bucket, move task to bucket, delete bucket | `SAFE_WRITE`; delete `DESTRUCTIVE` |
| Assignments / resources | `CAP-103`, `CAP-109` | assign, unassign, rebalance workload | `GOVERNED_WRITE` |
| Dependencies | `CAP-104` | link tasks (FS/SS/SF/FF), unlink | `GOVERNED_WRITE` |
| Scheduling | `CAP-107`, `CAP-108`, `CAP-114` | set dates, read timeline, read critical path, set calendar | read `READ`; edits `GOVERNED_WRITE` |
| Goals | `CAP-110` | link goal, update progress | `GOVERNED_WRITE` |
| Sprints | `CAP-111` | create sprint, move item, groom backlog | `GOVERNED_WRITE` |
| Custom fields | `CAP-112`, `CAP-113` | set field value, define field, set colouring rule | values `GOVERNED_WRITE`; schema `DESTRUCTIVE` |
| Portfolios | `CAP-116` | add/remove plan from portfolio, read roadmap | `GOVERNED_WRITE` |
| Reporting | `CAP-119`, `CAP-118` | read report, export | `READ`; import `DESTRUCTIVE` |
| Blueprints / reconciliation | `CAP-100`…`CAP-112` | apply blueprint, plan diff, reconcile to desired state | `GOVERNED_WRITE`, bulk paths `DESTRUCTIVE` |
| Governance | `CAP-117`, plus all | approve operation, read audit, read attestation posture | reads `READ`; sharing `GOVERNED_WRITE`/`DESTRUCTIVE` |

**TOOL-061 — Reconciliation is never destructive by default.** Drift resolution proposes a diff;
applying it is a separate, approved, per-target operation (vision: no destructive
re-application).

**TOOL-062 — Bulk is not a shortcut.** Any operation touching more than a configured number of
targets is `DESTRUCTIVE` regardless of the per-item class.

---

## 6. Tests

**TOOL-070** The registered catalog equals exactly the seventeen names of `TOOL-020`.
**TOOL-071** Every registered tool has a schema-valid `ExtendedToolManifest`.
**TOOL-072** Every tool declares `mutation_class`; a tool without one is not registered.
**TOOL-073** Every tool in 0.1.0 is `READ`; a non-read tool is denied by the policy engine.
**TOOL-074** No tool name matches the forbidden list of `TOOL-005`; no input or output schema
contains selector, DOM, cookie, token, URL or password fields.
**TOOL-075** `attestation_status` is derived from capability keys and cannot be hand-set.
**TOOL-076** Unknown tool names are denied by identity.
**TOOL-077** `planner_capabilities` output matches the capability matrix rows (`CAP-070`).
**TOOL-078** Auth tools reject any argument resembling a credential or MFA code.
**TOOL-079** `planner_project_snapshot` sets `partial: true` whenever a section is unattested.

---

## 7. Traceability

| ID range | Area |
| --- | --- |
| TOOL-001…007 | Surface rules |
| TOOL-010…014 | Manifest metadata |
| TOOL-020…021 | Catalog 0.1.0 definition |
| TOOL-030…035 | Platform tools |
| TOOL-040…045 | Authentication tools |
| TOOL-050…054 | Planner read tools |
| TOOL-055…057 | Errors and evidence |
| TOOL-060…062 | Future semantic catalog |
| TOOL-070…079 | Tests |


