# Observability

Observability covers structured logging, metrics, audit events and operational health for the
Planner MCP control plane and private browser worker. It must make behaviour diagnosable without
turning telemetry into a data-exfiltration channel.

Companions: [`security.md`](security.md), [`privacy-boundary.md`](privacy-boundary.md),
[`state-model.md`](state-model.md), [`testing.md`](testing.md) and [`reporting.md`](reporting.md).

## 1. Principles

- structured JSON logs only;
- redaction before emission, not only at the sink;
- fail closed if a value cannot be safely represented;
- low-cardinality metrics with a closed label allow-list;
- no passwords, cookies, auth headers, access/refresh tokens or browser session material;
- no raw HTML/screenshots/DOM dumps in normal telemetry;
- no task/plan/user/email/title/URL/operation identifiers in metric labels;
- health/readiness must reflect real component state without leaking tenant/session secrets;
- Graph-related telemetry, if Graph is ever used as an auxiliary path, is contextual only and never
  determines Planner capability success.

## 2. Canonical metrics

The initial required metric surface includes:

```text
planner_tool_calls_total
planner_tool_duration_seconds
planner_browser_operations_total
planner_auth_events_total
planner_mfa_required_total
planner_ui_validation_failures_total
planner_policy_decisions_total
planner_lock_events_total
```

Additional metrics may be added only with bounded labels and a documented cardinality budget.

### Allowed label examples

Safe low-cardinality dimensions include:

- service;
- tool name from the fixed catalogue;
- outcome/status enum;
- mutation class enum;
- auth state enum;
- blocker/error code enum;
- policy decision enum;
- resource **type** (not resource id);
- UI surface/contract fragment id only when the registry is bounded and reviewed.

### Prohibited metric labels

Never use:

- task IDs;
- plan IDs;
- dependency IDs;
- usernames/display names;
- email/UPN;
- titles/descriptions;
- complete URLs;
- operation IDs;
- MFA numbers;
- arbitrary exception strings.

Registration of a metric with an unapproved label key/value source fails tests/startup according to
the implementation policy.

## 3. Structured logging

Each log event uses a stable schema containing only fields appropriate to its event type. Typical
safe fields include:

```text
timestamp
level
service
version
event
tool
outcome
phase
duration_ms
attempt
error_code
mutation_class
policy_decision
redaction_count
```

`operation_id` may be present in logs as a correlation field if the privacy/security design accepts
it for that sink; it must **not** become a Prometheus label.

Human/business data is excluded or transformed to the minimum bounded representation needed for
operations. Log messages use static templates rather than interpolating raw request values.

## 4. Redaction

Redaction applies recursively to structured objects and exception handling.

Deny-listed classes include:

- password/secret/passphrase values;
- `Authorization` headers;
- access/refresh tokens;
- cookies/session/local-storage material;
- browser profile paths/content when they reveal personal data;
- private keys;
- email/UPN and display names unless an explicitly approved report/tool contract requires them;
- task titles/descriptions/comments/checklist content in system telemetry;
- attachment filenames/content;
- raw Planner deep-link paths/query strings;
- raw selectors/DOM/HTML in ordinary logs.

A redaction test suite must include adversarial nested structures and exception messages.

## 5. MFA observability

The normal log stream never contains the MFA number. The only place where the number may leave the
worker/control plane is the dedicated sanitized MFA notification event defined in
[`authentication-and-mfa.md`](authentication-and-mfa.md) and
[`hermes-integration.md`](hermes-integration.md).

Observability records only bounded states/counters such as challenge detected, expired, resumed or
authenticated.

MFA approval remains exclusively in Microsoft Authenticator.

## 6. UIContract/drift observability

Track bounded events for:

- fragment validation success/failure;
- attestation state changes;
- selector/semantic validation failures;
- `UI_DRIFT` blockers;
- affected capability state transitions;
- circuit-breaker open/close state where implemented.

A drift event does not trigger exploratory browser interaction. The affected path fails closed and
requires re-attestation.

## 7. Policy/approval/lock observability

Record bounded governance events:

- `ALLOW`, `DENY`, `REQUIRE_APPROVAL`;
- policy/rule identifier;
- approval requested/consumed/expired/replayed;
- lock acquired/conflict/expired/released;
- saga/checkpoint state transition;
- read-back verdict;
- `UNKNOWN_OUTCOME`.

Do not log approval payload values, tenant data or secret material merely to make the audit trail
more verbose.

## 8. Audit trail

Audit is a separate durable governance record, not a substitute for logs. It is append-oriented and
must support reconstruction of governed operations using bounded/sanitized data and evidence hashes.

Representative fields:

```text
audit_id
timestamp
operation_id
tool
mutation_class
policy_decision
approval_id
idempotency_fingerprint_hash
resource_type
before_hash
requested_hash
after_hash
read_back_verdict
checkpoint_state
error_or_blocker_code
contract_version
ui_contract_version
evidence_ref
```

The implementation should provide tamper-evidence (for example hash chaining) and a verifier. The
audit schema never includes credential/session secrets.

## 9. Health and readiness

`planner_health` answers process/liveness health. `planner_readiness` answers whether the service can
safely accept the relevant class of work.

Readiness may include non-secret facts such as:

- state DB/migration status;
- policy validity;
- browser-worker reachability;
- UIContract registry load status;
- configured mode (`read_only`, etc.);
- circuit-breaker state summary;
- external blocker code.

Readiness must not expose tokens, cookies, tenant content or personal identity data. In 0.1.0,
`AUTHENTICATED` is not necessarily a prerequisite for the service itself to be healthy, but live
Planner read tools may return an auth blocker until the browser session is ready.

## 10. Alerting principles

Alerts are based on conditions requiring operator action, for example:

- worker/browser unavailable or crash loop;
- repeated auth/session expiry;
- MFA challenge expiry;
- UI drift/attestation failure;
- policy invalid/missing;
- approval replay attempt;
- repeated lock conflicts/expired leases;
- redaction detector violation;
- audit integrity failure;
- persistent tool error/latency degradation;
- supply-chain/release gate failure where operationally monitored.

Hermes/Telegram may receive a sanitized notification copy; it is not the source of truth for
monitoring state.

## 11. Tracing

Distributed tracing may be added where it preserves the privacy/cardinality boundary. Trace context
can correlate:

```text
ChatGPT → Cloudflare → planner-mcp → browser worker
```

Span attributes follow the same deny-list as logs/metrics. No selector CSS/XPath, credential, task
content or session secret is placed in span attributes.

## 12. Reporting interface

Reporting consumes the semantic read/state/audit model, not browser selectors directly. Operational
reports may aggregate:

- tool outcomes/latency;
- auth/session health;
- UIContract/drift state;
- policy/approval/lock outcomes;
- reconciliation status;
- security/release gate state.

Business/project reports are separately defined in [`reporting.md`](reporting.md) and may return
request-scoped project data through semantic tools without making that data part of system telemetry.

## 13. Testing

Required observability tests include:

- adversarial redaction positive/negative cases;
- recursive/nested redaction;
- exception sanitization;
- metric label allow-list/cardinality checks;
- no prohibited ID/content labels;
- MFA number absent from general logs;
- audit integrity verification;
- UI drift produces bounded blocker telemetry and zero mutation after failure;
- reporting/telemetry generators do not invoke mutation paths.

## 14. Backlog mapping

Observability is cross-cutting but canonical ownership is primarily:

| Concern | P-key(s) |
| --- | --- |
| Structured logging/redaction foundation | P-008 |
| Prometheus metrics foundation | P-009 |
| Secret/telemetry hygiene gates | P-063 |
| Circuit breakers/retry operational state | P-066 |
| Audit trail completeness | P-067 |
| CI/release evidence | P-068, P-073, P-074 |
| Governance reporting | P-060 |

The mapping must not repurpose P-046..P-053; those keys belong to custom fields through
reconciliation/blueprint work in the canonical backlog.
