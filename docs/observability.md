# Observability

Scope: logging, metrics, tracing, audit trail and alerting for the `pestoura/planner-mcp` control plane and the `planner-browser-worker`. Companion documents: [architecture.md](architecture.md), [security.md](security.md), [privacy-boundary.md](privacy-boundary.md), [threat-model.md](threat-model.md), [browser-worker.md](browser-worker.md), [state-model.md](state-model.md).

Governing rule: the browser worker is the primary execution surface. Everything observable about a Planner mutation must be explainable from browser worker telemetry alone. Microsoft Graph telemetry is **contextual enrichment only** and never gates health, readiness or success determination.

## 1. Principles

| # | Principle | Consequence |
|---|-----------|-------------|
| O-1 | Structured only | No free-form `print`/unstructured logs anywhere in shipped code. |
| O-2 | Redact at construction | Redaction happens in the log record factory, not at the sink. A sink outage must never leak raw values. |
| O-3 | Low cardinality metrics | No task ids, plan ids, user ids, URLs or selectors in label values. |
| O-4 | Correlate by `operation_id` | Every log line, span, metric exemplar and audit row carries the same `operation_id`. |
| O-5 | Evidence-grade audit | The audit trail is append-only and sufficient to reconstruct what was changed in Planner and why. |
| O-6 | No screenshots by default | Visual evidence is opt-in, isolated-acceptance only, and never emitted to the log stream. |
| O-7 | Graph is contextual | Graph errors degrade enrichment fields; they never mark an operation failed. |

## 2. Structured log schema

Transport: one JSON object per line, UTF-8, newline delimited, written to stdout. No ANSI. No multi-line stack traces — exceptions are serialized into `error.stack` as an escaped string.

### 2.1 Envelope

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `ts` | string (RFC 3339, UTC, ms) | yes | Emitter clock. |
| `level` | enum `debug\|info\|warn\|error\|critical` | yes | |
| `service` | enum `planner-mcp\|planner-browser-worker` | yes | |
| `version` | string | yes | Semver + short git sha. |
| `env` | enum `dev\|ci\|isolated\|live` | yes | `live` enables strict redaction mode. |
| `event` | string (dotted, closed set) | yes | e.g. `tool.invoke`, `worker.step`, `ui.selector.miss`. |
| `msg` | string | yes | Static human string; no interpolated identifiers. |
| `operation_id` | string (ULID) | yes | Chain-wide correlation id. |
| `request_id` | string (ULID) | no | Per-HTTP-request id. |
| `session_id` | string (ULID) | no | Browser profile session. |
| `tool` | string | no | MCP tool name from [tool-catalog.md](tool-catalog.md). |
| `phase` | enum `plan\|precondition\|act\|read_back\|reconcile\|finalize` | no | |
| `outcome` | enum `ok\|noop\|retry\|denied\|failed` | no | Terminal-phase only. |
| `duration_ms` | integer | no | |
| `attempt` | integer | no | Retry counter, 1-based. |
| `idempotency_key_hash` | string (sha256 hex, 16 chars) | no | Never the raw key. |
| `resource` | object | no | See 2.2. |
| `error` | object | no | See 2.3. |
| `graph` | object | no | Contextual only; see 2.4. |
| `redactions` | integer | yes | Count of fields redacted in this record. `0` is meaningful. |

### 2.2 `resource` sub-object

| Field | Type | Notes |
|-------|------|-------|
| `kind` | enum `plan\|bucket\|task\|checklist_item\|attachment\|field\|view` | Low cardinality. |
| `id_hash` | string | sha256(id + per-deployment salt), 16 hex chars. |
| `title_len` | integer | Length only, never the title. |
| `premium` | boolean | Whether the resource requires Planner Premium semantics. |

### 2.3 `error` sub-object

| Field | Type | Notes |
|-------|------|-------|
| `class` | string | Exception class name. |
| `code` | string | Stable internal code, e.g. `WRK_SELECTOR_MISS`. |
| `retryable` | boolean | |
| `stack` | string | Escaped, trimmed to 4 KiB, paths relativized to repo root. |
| `selector_id` | string | Logical selector name from [ui-contract.md](ui-contract.md), never a raw CSS/XPath string. |

### 2.4 `graph` sub-object (contextual)

| Field | Type | Notes |
|-------|------|-------|
| `available` | boolean | |
| `latency_ms` | integer | |
| `status` | integer | HTTP status, if any. |
| `degraded_reason` | string | Closed set: `unauthorized`, `throttled`, `timeout`, `disabled`, `schema_mismatch`. |

A `graph.available=false` record is always `level<=warn`. It must never produce `outcome=failed`.

## 3. Redaction rules

Redaction is applied by a single `RedactingLogFactory` before serialization. Rejecting an unredactable value is preferred over emitting it.

| Class | Examples | Rule |
|-------|----------|------|
| Credentials | passwords, cookies, `Authorization`, refresh/access tokens, session storage blobs | Dropped entirely; replaced with `"[redacted:credential]"`. |
| MFA material | Authenticator number, challenge nonce | Allowed **only** in the sanitized MFA event (see [authentication-and-mfa.md](authentication-and-mfa.md)); never in general logs. |
| Personal data | display names, UPNs, e-mail addresses, avatar URLs | Replaced by `"[redacted:pii]"`; optionally a stable salted hash in `*_hash`. |
| Business content | task titles, descriptions, comments, checklist text, attachment filenames | Replaced by length + hash. Never verbatim. |
| Identifiers | plan/bucket/task GUIDs | Salted-hash only (`id_hash`). |
| URLs | Planner deep links | Scheme + host retained; path and query replaced by `/[redacted:path]`. |
| Selectors | CSS/XPath used by Playwright | Logical `selector_id` only. |
| Screenshots / DOM dumps | | Never in logs. Written to the isolated-acceptance evidence directory only, per [acceptance.md](acceptance.md). |

Redaction invariants tested in CI (see [testing.md](testing.md)):

1. A record containing a value matching any credential/PII detector fails the test suite.
2. `redactions` must equal the number of substitutions actually performed.
3. Salt is per-deployment, sourced from a secret, never logged; hashes are therefore not cross-deployment linkable.
4. `env=live` forbids `level=debug` emission of `resource.title_len` for premium fields flagged sensitive.

## 4. Metrics

Prometheus exposition on the worker's internal port and the control plane's loopback admin port. Public ingress never exposes `/metrics`. All histogram buckets are explicit; no default `le` sprawl.

### 4.1 Global label discipline

Allowed label keys, closed set: `service`, `env`, `tool`, `phase`, `outcome`, `resource_kind`, `error_code`, `selector_id`, `reason`, `surface`. Every label value comes from an enumerated set validated at registration time. Unbounded values are rejected at startup by the metrics registry guard.

### 4.2 Control plane metrics

| Name | Type | Labels | Meaning |
|------|------|--------|---------|
| `plannermcp_tool_invocations_total` | counter | `tool`, `outcome` | MCP tool calls. |
| `plannermcp_tool_duration_seconds` | histogram | `tool`, `phase` | End-to-end tool latency. Buckets: .1 .25 .5 1 2 5 10 30 60 120. |
| `plannermcp_tool_denied_total` | counter | `tool`, `reason` | Policy/authorization denials. `reason` ∈ `scope`, `readonly_mode`, `dry_run`, `unsupported_premium`, `rate_limit`. |
| `plannermcp_idempotency_outcomes_total` | counter | `outcome` | `outcome` ∈ `new`, `replayed`, `conflict`. |
| `plannermcp_reconcile_runs_total` | counter | `outcome` | See [reconciliation.md](reconciliation.md). |
| `plannermcp_reconcile_drift_items` | histogram | `resource_kind` | Drift items per run. Buckets: 0 1 2 5 10 25 50 100. |
| `plannermcp_graph_context_total` | counter | `outcome`, `reason` | Contextual Graph calls. Never used in SLOs. |
| `plannermcp_build_info` | gauge (=1) | `version`, `commit`, `env` | Static build identity. |

### 4.3 Browser worker metrics

| Name | Type | Labels | Meaning |
|------|------|--------|---------|
| `worker_operations_total` | counter | `tool`, `outcome` | Worker-side operations. |
| `worker_step_duration_seconds` | histogram | `phase` | Per-phase timing. Buckets: .05 .1 .25 .5 1 2 5 10 30. |
| `worker_selector_resolution_total` | counter | `selector_id`, `outcome` | `outcome` ∈ `hit`, `fallback`, `miss`. |
| `worker_read_back_total` | counter | `resource_kind`, `outcome` | Post-write verification result. |
| `worker_navigation_total` | counter | `surface`, `outcome` | `surface` ∈ `board`, `grid`, `timeline`, `task_detail`, `login`. |
| `worker_session_state` | gauge | `state` | `state` ∈ `cold`, `warming`, `ready`, `mfa_required`, `expired`. |
| `worker_mfa_events_total` | counter | `outcome` | `outcome` ∈ `raised`, `approved`, `expired`, `denied`. |
| `worker_browser_restarts_total` | counter | `reason` | `reason` ∈ `crash`, `oom`, `stale_profile`, `manual`. |
| `worker_queue_depth` | gauge | — | In-flight + queued operations. |

### 4.4 Cardinality budget

| Metric family | Worst-case series | Guard |
|---------------|-------------------|-------|
| Tool families | tools × outcomes ≈ 40 × 5 = 200 | Tool names are a closed catalog. |
| Selector family | selectors × 3 ≈ 120 × 3 = 360 | Selector ids come from the UI contract registry. |
| Everything else | < 300 | Registry guard fails startup above 2 000 total series. |

## 5. Tracing

OpenTelemetry, W3C `traceparent` propagated ChatGPT → Portal → control plane → worker. Sampling: parent-based, 100 % for mutating tools, 10 % for read-only tools, 100 % on error.

| Span | Emitter | Key attributes |
|------|---------|----------------|
| `mcp.tool` | control plane | `tool`, `operation_id`, `dry_run`, `outcome` |
| `mcp.policy` | control plane | `decision`, `reason` |
| `worker.operation` | worker | `tool`, `attempt`, `session_id` |
| `worker.navigate` | worker | `surface`, `selector_id` |
| `worker.act` | worker | `phase=act`, `resource_kind` |
| `worker.read_back` | worker | `outcome`, `mismatch_fields_count` |
| `graph.context` | control plane | `available`, `degraded_reason` |

Span attributes obey the same redaction rules as logs; attribute values are drawn from the metric label enumerations wherever possible. Exemplars link histograms to trace ids for mutating tools only.

## 6. Audit trail

Separate append-only store (SQLite WAL in single-node deployments), distinct from the log stream, retained longer, and never rotated by the log shipper.

| Column | Type | Notes |
|--------|------|-------|
| `audit_id` | ULID | Primary key. |
| `ts` | RFC 3339 | |
| `operation_id` | ULID | |
| `actor` | string | Portal-authenticated principal id (hashed). |
| `tool` | string | |
| `intent` | JSON | Normalized, redacted request parameters. |
| `preconditions` | JSON | Observed state hashes before mutation. |
| `effect` | JSON | Field-level before/after **hashes**, plus `changed_fields` names. |
| `read_back` | JSON | Verification result, per [state-model.md](state-model.md). |
| `evidence_ref` | string | Path/id of isolated-acceptance evidence bundle, if any. |
| `outcome` | enum | `ok\|noop\|failed\|denied`. |
| `graph_context` | JSON | Contextual snapshot; nullable. |

Properties: append-only (no UPDATE/DELETE grants), each row hash-chained to its predecessor (`prev_hash`, `row_hash`) so tampering is detectable, and exportable as NDJSON for [reporting.md](reporting.md).

## 7. Alerts

| Alert | Expression (intent) | For | Severity | Action |
|-------|---------------------|-----|----------|--------|
| `WorkerSessionNotReady` | `worker_session_state{state="ready"} == 0` | 10m | critical | Session re-auth per authentication-and-mfa. |
| `MfaBacklog` | `increase(worker_mfa_events_total{outcome="expired"}[30m]) > 0` | 0m | high | HITL notification via Hermes. |
| `SelectorMissSpike` | `rate(worker_selector_resolution_total{outcome="miss"}[15m]) > 0` | 15m | high | UI drift; freeze mutating tools, run selector attestation. |
| `ReadBackFailures` | `rate(worker_read_back_total{outcome!="ok"}[15m]) > 0.05` | 10m | critical | Halt mutations, open incident. |
| `ToolErrorRate` | `sum(rate(plannermcp_tool_invocations_total{outcome="failed"}[10m])) / sum(rate(plannermcp_tool_invocations_total[10m])) > 0.05` | 10m | high | Investigate. |
| `IdempotencyConflicts` | `increase(plannermcp_idempotency_outcomes_total{outcome="conflict"}[1h]) > 3` | 0m | medium | Inspect duplicate submissions. |
| `BrowserRestartLoop` | `increase(worker_browser_restarts_total[15m]) > 3` | 0m | high | Check resources / profile corruption. |
| `QueueSaturation` | `worker_queue_depth > 20` | 10m | medium | Throttle upstream. |
| `AuditChainBroken` | audit verifier job failure | 0m | critical | Security incident. |
| `RedactionViolation` | any log record failing the sink-side detector | 0m | critical | Stop shipping logs, rotate salt, incident. |

Explicitly **not** alertable: any `graph_*` degradation. Graph unavailability is informational by design.

## 8. Retention and access

| Stream | Retention | Access |
|--------|-----------|--------|
| Logs | 30 days | Operator, loopback/aggregator only. |
| Metrics | 90 days | Internal network only. |
| Traces | 14 days | Internal network only. |
| Audit | 400 days | Operator + governance review, export-only. |
| Evidence bundles | Per release + 2 | Attached to the release record, see [release-process.md](release-process.md). |

## 9. Backlog mapping

| Concern | Backlog keys |
|---------|--------------|
| Log schema + redaction factory | P-046, P-047 |
| Metrics registry + cardinality guard | P-048, P-049 |
| Tracing propagation | P-050 |
| Audit store + hash chain | P-051, P-052 |
| Alert rules + runbooks | P-053 |
