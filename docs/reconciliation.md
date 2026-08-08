# Reconciliation

Reconciliation is the preferred long-term execution model for Planner MCP: callers declare desired
project state, the control plane reads the current Planner state, normalizes it, computes a
deterministic diff, plans governed changes, executes only authorized steps, reads back every effect
and verifies convergence.

This document is normative with [`idempotency.md`](idempotency.md),
[`state-model.md`](state-model.md), [`governance.md`](governance.md),
[`security.md`](security.md) and ADR-003.

## 1. Release boundary

Release `0.1.0` remains **read-only**. Reconciliation infrastructure may exist for modelling,
normalization, diffing, planning, checkpoint design and mock-only execution, but:

- no public `planner_project_reconcile` mutation is registered;
- no tenant `apply` path is enabled;
- live Planner mutation acceptance is not part of 0.1.0;
- the presence of P-050 code is not evidence of live reconciliation support.

Live governed apply is introduced only in a later release after mutation gates and evidence exist.

## 2. Canonical loop

```text
Desired Project State
        ↓
Read Current Planner State
        ↓
Normalize
        ↓
Resolve stable identities/bindings
        ↓
Compute deterministic Diff
        ↓
Plan ordered Changes
        ↓
Policy
        ↓
Approval if required
        ↓
Acquire typed Locks
        ↓
Execute one Saga step
        ↓
Read-back from UI
        ↓
Verify / checkpoint
        ↓
Converged? ── yes → finish
        └──── no  → bounded re-plan or fail closed
```

No future mutation tool may bypass this safety path or an equivalent framework proven to enforce the
same invariants.

## 3. Stable identity

Managed resources use stable identities wherever the product exposes them:

- `source_id`: stable identifier supplied by the desired-state source;
- `external_id`: Planner resource identity observed through the UI;
- binding record: `(source_id, external_id, resource_type, scope, evidence_hash, status)`.

Human-readable names are not idempotency keys.

Binding states include:

| State | Meaning |
| --- | --- |
| `BOUND` | source and Planner identity are uniquely linked and verified |
| `ORPHANED` | a binding exists but the Planner resource is no longer observed |
| `AMBIGUOUS` | more than one candidate exists; no automatic choice is safe |
| `UNBOUND` | no known binding exists |

Rules:

- a unique, evidence-backed natural-key match may be proposed for adoption;
- more than one candidate returns `BLOCKER_AMBIGUOUS_MATCH`;
- an orphan is never silently recreated;
- a create is not attempted merely because a title/name was not found;
- binding evidence is refreshed by read-back, not by write-response optimism.

## 4. Normalization

Current and desired state are normalized before comparison. Normalization is deterministic and
idempotent.

Examples:

- dates/timestamps use explicit ISO/RFC 3339 representation;
- effort/duration include explicit units;
- dependency type is a closed enum: `FS`, `SS`, `SF`, `FF`;
- text comparison rules are documented per field rather than guessed;
- identifiers are treated as opaque unless the contract states otherwise;
- an unknown/ambiguous value yields `NORMALIZATION_FAILED`, not silent coercion.

The read model is the source for reconciliation. Reporting or browser selectors are never compared
directly.

## 5. Diff model

A diff records, per resource type:

- `create`;
- `update`;
- `delete`;
- `adopt`;
- `no_op`;
- `ambiguous`;
- `orphaned`;
- `normalization_failed`.

Each proposed change carries at minimum:

- `source_id` when available;
- `external_id` when known;
- resource type/scope;
- changed field names;
- normalized before/desired values or their governed representation;
- mutation class;
- reversibility;
- read-back strategy;
- approval requirement;
- UIContract fragment/version required to execute it.

Strict removal of Planner-only state is classified conservatively. Destructive removal is never
inferred from an omitted field unless the desired-state contract explicitly declares strict
ownership of that field/resource.

## 6. Planning and ordering

Plans are deterministic. For identical desired/current normalized state and contract versions, the
planned operation list and plan fingerprint are identical.

Typical dependency ordering:

1. container/plan existence;
2. buckets/structure;
3. tasks;
4. hierarchy/WBS;
5. dependency edges;
6. schedule/effort/duration;
7. assignments;
8. custom fields/formatting;
9. removals in a dependency-safe reverse order.

Dependency graph mutations validate acyclicity before any UI action. An invalid/dangling edge is a
planning blocker, not an execution experiment.

## 7. Policy and approval

Every planned mutation declares its governance metadata before execution:

- `mutation_class`;
- trust level;
- reversibility;
- idempotency class;
- policy decision: `ALLOW`, `DENY` or `REQUIRE_APPROVAL`;
- exact approval fingerprint when required.

Missing, invalid or inconsistent policy results in `DENY`.

Approval is bound to the exact plan/diff digest, is single-use and expires. If the baseline state or
operation arguments change, the approval is invalid and a new plan/approval is required.

## 8. Locks

Typed resource locks prevent two Planner MCP mutations from changing the same resource concurrently.
Canonical lock keys include:

```text
plan:<id>
task:<id>
dependency:<id>
portfolio:<id>
auth:<profile>
browser_profile:<profile>
```

Locks have TTL/leases and deterministic acquisition order. A lock expiring during an uncertain
mutation makes the operation outcome uncertain; the system re-reads before any continuation.

Locks protect against internal concurrency. Human or third-party edits in Planner are detected by
snapshot/read-back mismatch and are never overwritten blindly.

## 9. Sagas and checkpoints

Multi-step work is modelled as a saga. Each step records:

- intended operation/fingerprint;
- before snapshot/reference;
- policy/approval reference;
- lock scope;
- apply state;
- read-back evidence;
- checkpoint state;
- compensation state where a safe compensation exists.

Representative checkpoint states:

```text
PENDING
IN_PROGRESS
APPLIED
VERIFIED
PARTIAL
UNKNOWN_OUTCOME
FAILED
ROLLED_BACK
```

A write response alone can reach `APPLIED`, never `VERIFIED`. `VERIFIED` requires a fresh UI
read-back that matches requested state.

## 10. Read-back and retry

After every future mutation:

1. perform a fresh read from the UI through the normal read path;
2. normalize the observed state;
3. compare the intended changed fields and required guard fields;
4. record one of:
   - `VERIFIED` / converged;
   - not applied, safe retry may be considered according to idempotency class;
   - partial/mismatch;
   - `UNKNOWN_OUTCOME` when the state cannot be determined.

A timeout does **not** authorize an automatic retry. Read-back comes first. If read-back cannot
resolve the result, the operation remains `UNKNOWN_OUTCOME` and no blind retry occurs.

See [`idempotency.md`](idempotency.md).

## 11. Drift and contract pinning

A reconciliation plan pins:

- current snapshot hash;
- product/contract version;
- UIContract version/fragments;
- capability evidence state used by the plan.

If the UIContract drifts, return `UI_DRIFT` / `BLOCKER_UI_DRIFT` and fail closed. Do not click around
to discover a replacement control during a mutation.

If the Planner state changes between plan and apply, return a stale/concurrent-change condition and
re-plan from a fresh read rather than overwriting unseen work.

## 12. Compensation

Compensation is used only where the inverse action is known, policy-approved and itself verifiable.
Do not treat compensation as a database rollback.

If an operation is partially applied and safe compensation is unavailable:

- preserve the exact checkpoint;
- identify affected resource references in the bounded audit/evidence model;
- report residual state;
- stop dependent steps;
- require explicit follow-up/reconciliation.

Partial state is never hidden behind a generic success.

## 13. Dry-run

Future `planner_blueprint_plan` / reconciliation dry-run produces the deterministic proposed plan
without tenant mutation. It includes:

- normalized diff;
- ordered operation list;
- mutation classes;
- policy decisions;
- approvals that would be required;
- lock scopes;
- read-back strategies;
- destructive/irreversible warnings;
- plan fingerprint and source snapshot hash.

A later apply must bind to the approved dry-run fingerprint; changed arguments/baseline require a new
dry-run.

## 14. Recovery after crash/restart

On recovery:

- load non-terminal operations/sagas;
- re-read affected Planner state before retrying anything uncertain;
- never replay steps already verified;
- revalidate locks, policy, approval expiry and UIContract version;
- recompute the remaining diff;
- stop on ambiguity, drift or changed baseline.

This makes recovery convergent rather than replay-oriented.

## 15. Security/privacy constraints

Reconciliation state/evidence must not persist:

- passwords, tokens, cookies or auth headers;
- exported browser storage/session blobs;
- raw DOM or screenshots in normal audit records;
- unnecessary task descriptions/comments/attachment contents;
- sensitive identifiers in metric labels.

The control plane stores only the minimum state required for identity, governance, verification and
audit, under the retention rules in [`state-model.md`](state-model.md).

## 16. Backlog mapping

| Concern | Canonical P-key(s) |
| --- | --- |
| Stable binding registry | P-049 |
| Desired-state reconciliation engine | P-050 |
| Blueprint format/validation | P-051 |
| Dry-run planning/import safety | P-052 |
| Reconciliation status/resume | P-053 |
| Mutation safety framework used by apply | P-031 |
| Audit/policy support | P-061, P-062, P-067 |

ADR-003 defines reconciliation-first architecture. No live apply capability is claimed solely because
these backlog items exist or pass in mock acceptance.
