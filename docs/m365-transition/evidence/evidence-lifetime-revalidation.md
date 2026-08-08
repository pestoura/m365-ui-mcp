# CORE-020 — Evidence lifetime and revalidation policy

## Decision

UI capability evidence has a bounded, versioned lifetime. Expiration is evaluated at use time and feeds the existing `CORE-017` lifecycle; the evidence database remains append-only and is not rewritten merely because time has passed.

The policy is repository-controlled:

```text
contracts/ui_evidence_lifetime_policy.json
```

Current baseline:

```text
policy_id:                ui-evidence-lifetime-v1
max_age_seconds:          604800   # 7 days
expiry_state:             STALE
missing_evidence_state:   RE_ATTESTATION_REQUIRED
future_timestamp_state:   RE_ATTESTATION_REQUIRED
```

The seven-day value is an initial, reviewable control-plane policy. It is **not** inferred from Microsoft 365 behavior and is not a claim that the Planner or Outlook Web UI remains stable for seven days.

## Why policy is versioned in the repository

Evidence lifetime changes the effective support state of capabilities. It therefore belongs to the reviewed contract surface rather than an untracked runtime environment variable.

Every policy has a deterministic SHA-256 digest. A policy change requires the normal PR/CI/review path and produces a new digest visible in freshness assessments.

The implementation currently bounds `max_age_seconds` to:

```text
minimum: 60 seconds
maximum: 30 days
```

This prevents accidental zero/near-zero lifetimes and prevents effectively indefinite acceptance of old UI evidence.

## Evaluation model

For each fragment in the exact current `UIContractSet`:

```text
latest CORE-018 evidence
        +
versioned lifetime policy
        +
current UTC time
        ↓
effective fragment lifecycle
```

Closed freshness outcomes are represented by the existing lifecycle:

```text
HEALTHY
STALE
DRIFTED
RE_ATTESTATION_REQUIRED
```

with bounded reason codes:

```text
EVIDENCE_FRESH
EVIDENCE_EXPIRED
EVIDENCE_MISSING
EVIDENCE_TIMESTAMP_IN_FUTURE
SOURCE_STALE
SOURCE_DRIFTED
SOURCE_RE_ATTESTATION_REQUIRED
```

## Precedence and fail-closed rules

Source evidence already marked as degraded is never promoted by age evaluation:

```text
DRIFTED                  -> DRIFTED
RE_ATTESTATION_REQUIRED  -> RE_ATTESTATION_REQUIRED
STALE                    -> STALE
```

Only a source record currently marked `HEALTHY` is eligible for freshness evaluation.

For a healthy source record:

```text
recorded_at > now
    -> RE_ATTESTATION_REQUIRED

now >= recorded_at + max_age
    -> STALE

otherwise
    -> HEALTHY
```

There is no grace window in the current policy. At the exact expiry boundary, evidence becomes `STALE`.

A fragment with no evidence for the exact current contract-set digest is:

```text
RE_ATTESTATION_REQUIRED
```

This avoids treating absence as implicit freshness.

## Contract binding

Freshness evaluation accepts only records that match:

- the exact current `UIContractSet.digest()`;
- an existing fragment ID;
- the exact fragment version;
- scope;
- application;
- surface.

Duplicate records for the same fragment in one evaluation input are rejected. The normal path is to feed `CapabilityEvidenceStore.latest_records(contract_set)` to the evaluator.

Evidence for an older contract-set digest cannot become current merely because it is still within its age window.

## Capability-scoped degradation

The resulting fragment lifecycle map is projected through:

```text
UIContractSet.attestation_for_capability(..., lifecycle_by_fragment=...)
```

Therefore expiry remains dependency-scoped.

Example:

```text
planner.plan-surface -> HEALTHY
planner.task-surface -> STALE
```

produces:

```text
plans.read -> remains attested
 tasks.read -> degraded / stale
```

A stale task fragment does not globally disable unrelated Planner surfaces.

## Revalidation

Expiration does not mutate or delete the historical evidence row.

Recovery requires a new evidence event through the `CORE-019` attestation workflow:

```text
STALE
  ↓
controlled re-attestation campaign
  ↓
valid fresh LIVE_UI observation
  ↓
CORE-019 evaluation
  ↓
new CORE-018 HEALTHY evidence record
  ↓
freshness evaluation
  ↓
HEALTHY
```

Old evidence remains available as append-only metadata/evidence digests for traceability.

`DRIFTED` does not become healthy merely because enough time passes. It requires the explicit re-attestation lifecycle defined in `CORE-017/019`.

## No background tenant activity from CI

`CORE-020` defines *when* evidence must be revalidated. It does not grant a mechanism to contact Microsoft 365.

CI may test freshness deterministically with fixed timestamps and sanitized records. CI must never:

- log in to the real Microsoft 365 tenant;
- run a real browser attestation;
- approve MFA;
- bypass Conditional Access;
- refresh evidence by performing live UI actions.

Automated live revalidation remains dependent on the later browser/session/network gates, especially controlled egress in `CORE-025`.

Until real evidence is collected under those gates, the current Planner UI fragments remain `UNVERIFIED_LIVE` and no new live-support claim is made by `CORE-020`.

## Data minimization

Freshness assessment operates only on existing CORE-018 metadata:

- fragment metadata;
- contract-set digest;
- evidence digest/ID;
- lifecycle state;
- UTC timestamp.

It introduces no tenant content, authenticated URL, screenshot, DOM, account/container identifier, cookie, token or browser storage state.

## Acceptance coverage

`tests/test_evidence_freshness.py` validates at least:

- deterministic loading/digest of the default policy;
- bounded policy lifetime;
- rejection of unsafe policy states and unknown fields;
- fresh evidence remains `HEALTHY`;
- exact expiry becomes `STALE`;
- missing evidence requires re-attestation;
- future timestamps fail closed;
- pre-existing `STALE`, `DRIFTED` and `RE_ATTESTATION_REQUIRED` are never promoted;
- wrong contract-set binding and duplicate records are rejected;
- stale evidence degrades only dependent capabilities;
- CORE-018 append-only history remains intact while the latest record is evaluated.

## Compatibility

`CORE-020` changes no public MCP tool or Planner semantic capability key.

Invariants remain:

```text
17 planner_* public tools -> PRESERVE
11 Planner capability keys -> preserved
10 historical selectors -> preserved
Outlook -> RESERVED / zero public tools
CORE-025 -> mandatory before automated live M365 egress/revalidation
```

## Phase 2 exit condition

Phase 2 can close only after the CORE-020 PR and post-merge `main` both pass all applicable repository gates, including:

```text
compile
lint
mypy
contract/schema validation
pytest
isolated acceptance
secret/dependency scanning
container builds
Trivy HIGH/CRITICAL
CycloneDX SBOM
canonical documentation
```

A gate not executed is not a PASS.
