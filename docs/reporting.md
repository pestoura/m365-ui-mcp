# Reporting

Scope: the reports `pestoura/planner-mcp` produces — operational, governance, evidence and portfolio — their formats, generation paths, redaction constraints and consumers. Companions: [observability.md](observability.md), [acceptance.md](acceptance.md), [governance.md](governance.md), [privacy-boundary.md](privacy-boundary.md), [reconciliation.md](reconciliation.md).

Rule inherited from the privacy boundary: **reports are derived artifacts, not new data channels.** A report may never contain a value that could not appear in a redacted log record, unless the report is explicitly classified `internal-detailed` and stays on the host.

## 1. Report classes

| Class | Audience | Contains | Leaves the host |
|-------|----------|----------|-----------------|
| `operational` | operator | metrics rollups, error taxonomy, session health | yes (redacted) |
| `governance` | project governance | capability matrix, backlog burn-up, gate status | yes (redacted) |
| `evidence` | release record | acceptance bundles, attestation reports | yes, attached to a release |
| `internal-detailed` | operator, on-host only | full drift detail with resolved titles | **no** |
| `client-facing` | ChatGPT/user, via a tool response | task-level answers scoped to the request | yes, request-scoped |

## 2. Operational reports

### 2.1 Daily operations digest

Generated from Prometheus and the audit store; emitted as Markdown and NDJSON.

| Section | Content |
|---------|---------|
| Availability | Uptime, worker session state timeline, browser restarts by reason |
| Throughput | Tool invocations by tool and outcome |
| Latency | p50/p90/p99 per tool and per phase |
| Reliability | Failure rate, retry rate, read-back mismatch count |
| UI health | Selector hit/fallback/miss counts by `selector_id` |
| MFA | Challenges raised/approved/expired |
| HITL | Requests, approvals, rejections, median wait |
| Graph context | Availability percentage, clearly labelled non-gating |
| Anomalies | Alerts fired, with links to runbooks |

### 2.2 Incident report

Produced per incident, structured for post-mortem: timeline by `operation_id`, affected operations from the audit export, root cause, blast radius (counts of resources touched, never their content), remediation, and the prevention item filed against the backlog.

### 2.3 Selector drift report

Generated whenever `worker_selector_resolution_total{outcome!="hit"}` is non-zero over a window.

| Column | Notes |
|--------|-------|
| `selector_id` | Logical name. |
| `surface` | Board/grid/timeline/task detail. |
| `hits`, `fallbacks`, `misses` | Counts over the window. |
| `first_seen`, `last_seen` | Timestamps. |
| `owner` | From the selector registry. |
| `action` | `monitor`, `patch`, `freeze`. |

A report containing any miss automatically proposes freezing mutating tools and re-running attestation per [testing.md](testing.md).

## 3. Governance reports

### 3.1 Capability matrix report

The single authoritative statement of what this project can do. One row per Planner Premium capability from [planner-premium-capabilities.md](planner-premium-capabilities.md).

| Column | Source |
|--------|--------|
| Capability | Capabilities doc |
| Tool(s) | [tool-catalog.md](tool-catalog.md) |
| Status | `unsupported` / `mock-verified` / `live-read-verified` / `live-verified` |
| Evidence ref | Acceptance bundle id |
| Last verified | Bundle timestamp |
| Backlog keys | P-keys |

Generation is automated from evidence manifests; a status may never be hand-edited upward. A CI check fails if any status in the published docs exceeds what the referenced evidence supports — this is the mechanism that enforces "never claim live support without browser evidence".

### 3.2 Backlog and roadmap status

Derived from the backlog (P-001..P-074) and [roadmap.md](roadmap.md): per-epic completion, critical-path position, blocked items with reasons, and gate status per phase. Rendered as a table plus a compact burn-up.

### 3.3 Security posture report

| Item | Source |
|------|--------|
| Image digests in use | `environment.json` / running stack |
| SBOM diff since last release | CI artifact |
| Known vulnerabilities by severity | Scanner output |
| Hardening assertions | Compose-lint results |
| Secret age / rotation due | Operator register |
| Open threat-model gaps | [threat-model.md](threat-model.md) |

## 4. Evidence reports

Evidence reports are the acceptance bundles described in [acceptance.md](acceptance.md) plus two rollups:

| Rollup | Content |
|--------|---------|
| Release evidence index | One row per bundle: level, sha, criteria pass counts, operator, chain head |
| Attestation history | Selector attestation results over time, showing UI stability trend |

Both are append-only and referenced from the release record ([release-process.md](release-process.md)).

## 5. Reconciliation reports

Produced by each reconciliation run (see [reconciliation.md](reconciliation.md)).

| Field | Notes |
|-------|-------|
| `run_id`, `started_at`, `duration_ms` | |
| `scope` | Plan hash, resource kinds examined |
| `counts` | `examined`, `equivalent`, `divergent`, `missing`, `extra` |
| `items` | Per item: `resource_kind`, `id_hash`, `divergent_fields` (names only), `proposed_action` |
| `applied` | Empty unless the run was authorized to remediate |
| `graph_context` | Optional, labelled non-authoritative |

The `internal-detailed` variant resolves `id_hash` to titles for operator use and is written only to the host evidence directory, never shipped.

## 6. Client-facing responses

Tool responses returned through the Portal to ChatGPT are themselves a reporting surface and obey stricter rules than logs, because they legitimately carry business content the user asked for.

| Rule | Detail |
|------|--------|
| Scope | Only resources the request targeted; no incidental enumeration of unrelated plans. |
| Minimization | Return the fields the tool contract declares; no raw DOM, no internal ids beyond what the contract specifies. |
| No secrets | Never any session, token, cookie, or configuration value. |
| No internals | No stack traces, selectors, file paths, or worker URLs; errors map to the public taxonomy. |
| Provenance | Every response includes `operation_id` and, for mutations, the read-back verdict. |
| Graph labelling | Any contextual Graph-derived field is explicitly flagged as contextual. |

## 7. Formats

| Format | Used for | Notes |
|--------|----------|-------|
| NDJSON | machine-readable exports (audit, logs, reconciliation items) | Stable field names, schema-versioned |
| Markdown | human-readable digests and summaries | Tables preferred; no images |
| JSON | manifests, attestation reports | Schema-validated in CI |
| Prometheus text | metrics snapshots inside evidence bundles | Raw exposition, unmodified |
| CSV | optional spreadsheet export of the capability matrix | Generated, never authored |

Every machine-readable report carries `schema_version`, `generated_at`, `generator_version`, and `source_range` (time window or git sha).

## 8. Generation and scheduling

| Report | Trigger | Generator |
|--------|---------|-----------|
| Daily digest | cron, 06:00 local | control-plane admin command |
| Selector drift | alert-driven + weekly | admin command |
| Reconciliation | per run | reconciliation job |
| Capability matrix | per evidence bundle close + per release | CI |
| Backlog/roadmap status | per PR merge to main | CI |
| Security posture | per release + weekly scan | CI |
| Incident | manual | operator, from templates |

Generators are read-only with respect to Planner: no report generation may invoke a mutating tool. This is asserted by a contract test that runs each generator against a stack where mutating handlers are unregistered.

## 9. Retention and distribution

| Report | Retention | Distribution |
|--------|-----------|--------------|
| Daily digest | 90 days | Operator; optional Hermes summary notification (counts only) |
| Incident | indefinite | Governance |
| Selector drift | 180 days | Operator |
| Capability matrix | versioned in the repo | Public docs |
| Evidence bundles | per release + 2 | Release record |
| `internal-detailed` | 30 days | On-host only, 0700 |

Hermes may receive only *counts and severities* from any report — never rows, never content — consistent with [hermes-integration.md](hermes-integration.md).

## 10. Verification

| Check | Level |
|-------|-------|
| Every generated report passes the redaction detector | unit + isolated acceptance |
| Capability matrix cannot exceed evidence | CI gate |
| Report schemas validate against fixtures | schema tests |
| Generators perform zero mutations | contract test |
| `internal-detailed` reports are never written outside the evidence dir | unit test on the writer |

## 11. Backlog mapping

| Item | Backlog keys |
|------|--------------|
| Report generator framework + schemas | P-068, P-069 |
| Capability matrix automation + CI gate | P-074 |
| Reconciliation reporting | P-028, P-029 |
| Evidence index + attestation history | P-070, P-072 |
| Operational digest + drift report | P-053, P-069 |
