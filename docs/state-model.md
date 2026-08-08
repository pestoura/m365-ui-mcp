# State Model

Persistent state belongs to the Planner MCP control plane. The browser worker remains stateless
apart from its dedicated persistent professional Chromium profile. SQLite is the initial state store,
with versioned, forward-only migrations.

This document is normative with [`reconciliation.md`](reconciliation.md),
[`idempotency.md`](idempotency.md), [`governance.md`](governance.md),
[`authentication-and-mfa.md`](authentication-and-mfa.md) and [`security.md`](security.md).

## 1. State-store principles

- persist only what is required for orchestration, governance, idempotency, locks, evidence pointers
  and audit;
- never persist Microsoft passwords, access tokens, refresh tokens or exported browser cookies;
- keep application state separate from the browser profile volume;
- every schema change is migration-managed and versioned;
- invalid/missing schema/configuration fails startup closed;
- operation/saga state must make partial and uncertain outcomes explicit;
- identifiers/content used only for telemetry must be minimized or hashed according to the privacy
  boundary.

## 2. Authentication state

`auth_state` stores only non-secret orchestration facts:

- profile identifier;
- formal auth state;
- reason/blocker code;
- last verified timestamp;
- non-secret expiry hint where safely derivable.

Canonical auth states are:

```text
UNKNOWN
READY
AUTH_REQUIRED
MFA_REQUIRED
WAITING_FOR_MFA
AUTHENTICATED
SESSION_EXPIRED
AUTH_FAILED
```

Rules:

- `AUTHENTICATED` requires positive browser evidence;
- absence of a login form is not evidence of authentication;
- no cookie/token value is read into or serialized by the control plane;
- Conditional Access requiring managed/compliant/enrolled/certificate-backed device records
  `BLOCKER_CONDITIONAL_ACCESS` and no bypass state.

## 3. Resource binding

A `binding` record supports stable identity and reconciliation:

```text
source_id
external_id
resource_type
scope
status
first_seen_at
last_verified_at
evidence_hash
```

Binding status is one of `BOUND`, `ORPHANED`, `AMBIGUOUS`, `UNBOUND`.

The store never uses a human-readable title as the unique idempotency identity. An ambiguous match
is stored/reported explicitly and blocks mutation.

## 4. Operation state

Every future mutation and governed multi-step action records an operation envelope including:

```text
operation_id
idempotency_key / fingerprint
tool_name
mutation_class
requested_state_ref
before_snapshot_ref
policy_decision
approval_id
state
after_snapshot_ref
verification_result
error_code
contract_version
ui_contract_version
started_at
ended_at
```

Canonical operation lifecycle states include:

```text
NOT_STARTED
IN_PROGRESS
APPLIED
VERIFIED
PARTIAL
UNKNOWN_OUTCOME
FAILED
ROLLED_BACK
```

Rules:

- `APPLIED` means the UI action appears to have been submitted; it is not success evidence;
- `VERIFIED` requires fresh UI read-back matching requested state;
- `UNKNOWN_OUTCOME` blocks blind retry;
- transition validation is enforced by the state layer;
- operation rows never include raw passwords/tokens/cookies/HTML/screenshot content.

## 5. Idempotency state

An `idempotency_record` contains at minimum:

```text
fingerprint
operation_id
state
result_hash
created_at
completed_at
ttl
```

Representative states:

- `IN_PROGRESS`;
- `VERIFIED` / completed;
- `FAILED`;
- `UNKNOWN_OUTCOME`.

Duplicate/uncertain behavior follows [`idempotency.md`](idempotency.md). A verified request may be
answered from its stored result reference without repeating the tenant action. An uncertain request
requires read-back/reconciliation before continuation.

## 6. Typed locks

Locks are keyed by resource type/id and include:

```text
resource_type
resource_id
mode
holder_operation_id
acquired_at
expires_at
```

Canonical resource namespaces include:

```text
browser_profile:<id>
auth:<id>
plan:<id>
task:<id>
dependency:<id>
portfolio:<id>
```

A write holds its exclusive resource lock across apply and read-back. Lock acquisition uses a fixed
order to avoid deadlocks. Expired lease during uncertain work forces re-read before continuation.

The state store does not pretend to lock human edits or third-party automation in Planner; those are
detected by baseline/read-back drift.

## 7. Saga and checkpoint state

Multi-step work stores a `saga` and ordered `saga_step` records.

A saga records:

- saga/run id;
- source/blueprint reference;
- desired-state fingerprint;
- baseline snapshot hash;
- contract/UIContract versions;
- overall state;
- creation/update timestamps.

Each step records:

- sequence;
- operation id;
- resource scope;
- checkpoint state;
- verification result;
- compensation state/evidence.

A saga is complete only when every required mutating step is `VERIFIED` or an explicitly defined
non-mutating step is complete. Partial/unknown steps keep the saga non-terminal.

## 8. Approval state

Approval storage follows [`governance.md`](governance.md). Records are:

- persistent;
- bound to an exact operation/diff fingerprint;
- expiring;
- single-use;
- atomically consumed;
- non-replayable.

A changed request/baseline does not inherit an earlier approval.

## 9. UIContract state

`ui_contract_state` tracks, per fragment:

```text
fragment_id
ui_contract_version
attestation_status
evidence_hash
last_validated_at
expires_at
confidence
drift_state
```

Selectors themselves remain version-controlled in the centralized UIContract/selector registry.
State records contain attestation/evidence metadata only.

A drift event causes dependent capability state to become `UI_DRIFT` and blocks execution until a
new validated contract/evidence record exists.

## 10. Capability state

Capability state is evidence-driven and may include:

```text
capability_id
tenant_license_observation
ui_observed
ui_contract_fragment
read_evidence
mutation_evidence
support_state
blocker_code
evidence_hash
last_validated_at
```

Canonical support states include:

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

Microsoft Graph availability is not a decisive field and never gates state promotion.

## 11. Snapshots

`planner_project_snapshot` produces a normalized composite read with a deterministic
`snapshot_hash`. The snapshot model includes only fields required by the semantic read/reconciliation
contract.

Rules:

- identical normalized state yields identical hash;
- degraded/unavailable contributing capabilities are explicit, not silently omitted;
- snapshots used for mutation/reconciliation are pinned to the operation plan;
- a changed baseline before apply triggers re-plan rather than overwrite;
- long-term persistence of tenant/business content is minimized and governed by retention policy.

## 12. Audit state

Audit evidence is append-only at the application contract level and reconstructs governed actions
without requiring raw log content. It records, as safely representable:

- operation id/tool;
- policy decision and rule;
- approval reference;
- idempotency/lock/checkpoint references;
- requested/before/after state hashes or bounded field metadata;
- read-back verdict;
- stable error/blocker codes;
- timestamps/versions/evidence references.

No raw credential/session material is part of audit state.

## 13. Retention

Default retention is configuration/policy-driven and documented. Baseline guidance:

| State | Retention principle |
| --- | --- |
| auth_state | rolling current state only; no session secret material |
| locks | lease/TTL only |
| idempotency records | bounded TTL sufficient for replay protection |
| operations/sagas/approvals/audit | retained for the approved operational/audit period |
| bindings | while resource relationship remains relevant, with stale/orphan handling |
| capability/UIContract evidence metadata | retained across releases as audit history |
| cached snapshots containing business data | short TTL/minimized; avoid long-term duplication |

Deletion/compaction itself must not make release/audit evidence unverifiable.

## 14. Migrations

Migrations are:

- versioned;
- forward-only;
- idempotent where possible;
- checksummed;
- serialized by a migration lock;
- applied before readiness becomes true;
- non-destructive by default.

A destructive/lossy schema migration requires an ADR and an explicit migration/rollback plan. An
already-applied migration whose checksum unexpectedly changes causes startup failure.

`planner_readiness` exposes non-secret schema/migration readiness facts.

## 15. Privacy boundary — never stored

The state database must never contain:

- Microsoft password;
- access/refresh token;
- raw cookie or exported storage state;
- authorization header;
- browser profile/session blob;
- private keys;
- raw screenshots/DOM dumps as state rows;
- full browser HTML containing tenant/business data;
- personal-home/credential material copied from the host.

Task/user/business content is persisted only when a specific semantic feature requires it and after
privacy/storage rules are documented; the default is identifiers, normalized bounded fields and
hash/evidence references rather than duplicate content stores.

## 16. 0.1.0 boundary

State structures for approvals, idempotency, locks, sagas and reconciliation may exist as foundations
in 0.1.0, but public tools remain the canonical 17 `READ` tools. No state-table presence authorizes a
live write path.

## 17. Backlog mapping

| Concern | Canonical P-key(s) |
| --- | --- |
| State store/migrations | P-006 |
| Auth lifecycle persisted facts | P-018, P-022 |
| Stable project snapshot | P-030 |
| Mutation framework state | P-031 |
| Binding registry | P-049 |
| Reconciliation/checkpoint state | P-050, P-053 |
| Policy/approval state | P-061, P-062 |
| Audit completeness | P-067 |

Implementation must keep this mapping synchronized with [`backlog.md`](backlog.md) and
[`traceability.md`](traceability.md).
