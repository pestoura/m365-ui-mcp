# Reporting

Reporting is produced from the semantic Planner read/state/audit models. It must never query browser
selectors directly as a reporting API and must never become a side channel for secrets/session data.

Companions: [`observability.md`](observability.md), [`state-model.md`](state-model.md),
[`planner-premium-capabilities.md`](planner-premium-capabilities.md),
[`reconciliation.md`](reconciliation.md), [`privacy-boundary.md`](privacy-boundary.md) and
[`release-process.md`](release-process.md).

## 1. Reporting principles

- consume normalized semantic data, not DOM/selectors;
- return only data authorized by the tool/report scope;
- include freshness/evidence/capability-state context;
- mark provisional/degraded sections explicitly;
- no secret, cookie, token, browser profile/session or internal selector material;
- system telemetry reports use minimized/redacted data;
- project/business reports may contain the project data legitimately requested by the user, but do
  not copy that content into system logs/metrics as a side effect;
- no report generator may invoke a mutation path.

## 2. Future project-report models

The product roadmap includes semantic reports for:

- project status;
- milestones;
- schedule variance;
- overdue tasks;
- workload/people allocation;
- dependencies/blockers;
- critical path;
- sprint/backlog status;
- portfolio status;
- executive summary.

These reports are enabled only as their contributing Planner capabilities become evidenced and
supported.

## 3. Common report envelope

Machine-readable reports should use a versioned envelope including as appropriate:

```text
report_type
schema_version
generated_at
source_snapshot_hash
source_freshness
capability_states
provisional_sections
warnings/blockers
data
```

The report must identify when a contributing capability is unavailable, degraded, unverified or
stale rather than silently omitting that part of the analysis.

## 4. Project status report

Candidate sections:

- project/plan summary;
- task counts by state;
- overdue/near-due tasks;
- milestone status;
- blocker/dependency summary;
- schedule/effort variance where the relevant baseline/capability exists;
- open risks/unknowns inferred only from supported semantic fields;
- freshness/evidence state.

Do not invent a schedule baseline if Planner/the desired-state model does not provide one.

## 5. Milestone and schedule reporting

Milestone/schedule reports depend on evidenced support for the relevant Planner Premium semantics.
They may include:

- milestone list/status;
- planned/current dates;
- schedule variance;
- critical/near-critical indicators if directly supported/evidenced;
- dependency blockers;
- unresolved schedule fields.

A locally calculated critical path must not be presented as “Planner critical path” unless that
calculation is an explicitly separate product feature and clearly labelled. If the product reads
Planner's own critical-path indicator, report it as observed Planner state.

## 6. Workload reporting

Workload/people reports are privacy-sensitive and require minimization. They may aggregate:

- assignment counts;
- capacity/load measures exposed by supported Planner semantics;
- overloaded/unassigned work;
- plan/portfolio aggregate status.

User identity/display data is returned only when required by the requested semantic report and
allowed by policy; it is not copied into metrics labels/system logs.

## 7. Sprint/backlog reporting

When sprint/backlog capability is live-evidenced, reporting may include:

- sprint scope/dates/status;
- committed/completed/remaining task counts;
- blocked/overdue sprint items;
- backlog size and movement;
- freshness/capability warnings.

Do not infer unsupported Scrum metrics from fields that do not semantically represent them.

## 8. Portfolio reporting

Portfolio/roadmap reports consume supported portfolio membership plus project summaries.

Rules:

- missing/blocked projects are listed explicitly;
- no plan is silently dropped because its read failed;
- aggregate status includes data freshness;
- project-level detail is included only as required by the report contract;
- portfolio mutation/restructure is never triggered by report generation.

## 9. Executive summary

An executive summary is a derived presentation layer over semantic reports. It may summarize:

- overall project/portfolio health;
- major milestones;
- schedule/overdue indicators;
- blockers/dependencies;
- workload concerns;
- decisions requiring attention;
- evidence/freshness limitations.

It must distinguish observed facts from derived/inferred narrative. Unsupported/unverified fields are
not filled with plausible guesses.

## 10. Operational/security reporting

Separate operational reports may summarize:

- service health/readiness;
- tool volume/latency/error rates;
- auth/session events;
- UIContract/drift state;
- policy/approval/lock outcomes;
- acceptance/release gate status;
- supply-chain scan/SBOM status;
- audit integrity.

These reports use redacted telemetry and do not expose project content unless the report explicitly
has a business-report authorization scope.

## 11. Capability matrix report

The capability matrix is generated from the capability/evidence state, not hand-edited upward.

Recommended columns:

```text
capability
tenant/license observation
UI observed
UIContract fragment/version
read evidence
mutation evidence
support state
blocker/degradation
last validated
evidence reference
```

Canonical states are:

```text
UNVERIFIED_LIVE
DISCOVERED
READ_ATTESTED
MUTATION_ATTESTED
SUPPORTED
DEGRADED
UI_DRIFT
BLOCKED_CONDITIONAL_ACCESS
```

Graph availability is not a decisive reporting column.

## 12. Reconciliation report

Future reconciliation reports include:

- run/saga id;
- source snapshot/fingerprint;
- examined resource counts;
- create/update/delete/adopt/no-op/ambiguous/orphan counts;
- planned operation classes;
- policy/approval summary;
- checkpoint state;
- verified/partial/unknown outcome;
- residual state requiring operator action.

The public/sanitized form avoids raw tenant/business content where counts/hashes/references are
sufficient. A request-scoped detailed diff may return semantic project fields according to policy.

## 13. Release/evidence reporting

Release reports index:

- exact git SHA/version;
- required gate results;
- IA-01..IA-16 outcome;
- live read-only evidence where performed;
- image digests;
- control-plane/browser-worker SBOM references;
- vulnerability findings/exceptions;
- capability matrix delta;
- known blockers/limitations.

A required gate that did not run is rendered `BLOCKED`/`UNAVAILABLE`, never green.

## 14. Formats

Supported future formats may include:

- JSON for tool/API responses and manifests;
- Markdown for human summaries;
- CSV for bounded tabular exports where appropriate;
- NDJSON for audit/evidence exports;
- Prometheus text only for metrics snapshots, not business reports.

Every machine-readable report is schema-versioned.

## 15. Retention/distribution

Retention/distribution follows the data class:

- operational aggregates: bounded according to observability policy;
- release/evidence indexes: retained with releases;
- request-scoped project reports: not automatically retained as system telemetry;
- detailed local evidence: host-only/controlled, minimized and time-bounded;
- exports: explicit user action/path, restrictive permissions, no automatic commit/upload.

Hermes may receive only a specifically sanitized notification/summary payload defined by
[`hermes-integration.md`](hermes-integration.md), not arbitrary report rows/project content.

## 16. Verification

Report tests include:

- schema validation;
- generator performs zero mutation calls;
- capability/evidence status cannot be raised by report code;
- missing/degraded input capability is visible in output;
- freshness is present;
- telemetry-safe report classes pass redaction tests;
- project report responses stay within requested/policy scope;
- no selector/browser internals leak into user reports;
- export path/content is not logged unnecessarily.

## 17. Backlog mapping

Reporting/portfolio ownership is canonically EPIC-08:

| Concern | Canonical P-key(s) |
| --- | --- |
| Portfolio and roadmap reads | P-054 |
| Snapshot history | P-055 |
| Status and variance reports | P-056 |
| Portfolio rollup | P-057 |
| Sharing/permissions governance feeding reports | P-058 |
| Controlled export/reporting surfaces | P-059 |
| Governance reporting | P-060 |

Cross-cutting release/capability reporting also depends on P-068..P-074. Reporting must not reuse
P-068/P-069 as “report generator” work; those keys are canonically CI and isolated acceptance.
