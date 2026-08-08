# RB-M365-UI-ATTEST-001 — UI capability attestation

Status: `CORE-019`

## Purpose

Provide a deterministic and reproducible workflow for UIContract discovery and attestation without exposing a generic browser executor and without allowing mock evidence to promote live support.

The workflow has two deliberately separated layers:

1. **repository-side planning/evaluation** — available through `scripts/attest_ui_contract.py` and safe to exercise in CI with mock/sanitized fixtures;
2. **live observation collection** — an operational activity against the dedicated authenticated Microsoft 365 browser profile and **never executed by CI against a real tenant**.

`CORE-019` does not create live Microsoft 365 egress. Controlled worker egress remains a `CORE-025` prerequisite for an automated live campaign.

## Safety invariants

The runbook must never collect, persist or publish:

- authenticated screenshots;
- raw DOM;
- page text or mailbox/calendar/contact content;
- cookies, access/refresh tokens or browser storage state;
- account, tenant or container identifiers;
- raw authenticated URLs;
- caller-supplied CSS/XPath/JavaScript/browser actions.

Structural observations are represented only by SHA-256 digests after text and attribute values have been removed at capture time.

Mock observations may validate the evaluator but can never produce a live `HEALTHY` promotion.

## Current contract condition

At the start of `CORE-019`, the four current fragments are:

```text
common.auth
planner.plan-surface
planner.task-surface
planner.account
```

The current selectors are still `UNVERIFIED_LIVE` and do not yet contain attested locator plans. Therefore the first real campaign is expected to be `DISCOVERY`; no tool may invent locator values to skip that stage.

## Tooling

The repository-side command is:

```text
python scripts/attest_ui_contract.py plan [--level LEVEL] [--fragment ID ...]
python scripts/attest_ui_contract.py evaluate OBSERVATION.json [--state /absolute/path/evidence.db]
```

Closed levels:

```text
DISCOVERY
UI
READ
MUTATION
```

These are **evidence maturity levels**, not a second runtime state machine. Runtime health remains governed by the `CORE-017` lifecycle:

```text
HEALTHY
STALE
DRIFTED
RE_ATTESTATION_REQUIRED
```

## 1. Generate a campaign

Example:

```text
python scripts/attest_ui_contract.py plan \
  --level DISCOVERY \
  --fragment planner.task-surface
```

The output is deterministic for the exact UIContractSet. It contains:

- `campaign_id`;
- exact `contract_set_digest`;
- requested evidence level;
- ordered fragment IDs;
- ordered selector keys;
- selector contract status;
- declared locator strategy names only;
- `discovery_required`.

It intentionally does **not** expose locator values or accessible names.

Changing contract semantics changes the contract-set digest and therefore the campaign identity.

## 2. Collect a live observation

Live collection is performed only in the dedicated professional Microsoft 365 browser context after the relevant browser/session/network gates are satisfied.

A sanitized observation contains only:

```text
campaign_id
contract_set_digest
fragment_id
fragment_version
target_level
source
observed_at
selector_observations
locale (optional)
ui_surface_signal_digest (optional)
read_probe_ok (READ/MUTATION when applicable)
mutation_applied (MUTATION only)
read_back_ok (MUTATION only)
compensation_proven (MUTATION only)
approval_digest (MUTATION only)
```

Each selector observation contains only:

```text
selector_key
result
structural_digest
```

Closed selector outcomes:

```text
UNIQUE_MATCH
NO_MATCH
AMBIGUOUS
STRUCTURE_MISMATCH
```

A `UNIQUE_MATCH` requires a structural SHA-256 digest. Raw page evidence is never accepted by the evaluator.

### Observation skeleton

```json
{
  "campaign_id": "sha256:<campaign digest>",
  "contract_set_digest": "sha256:<contract-set digest>",
  "fragment_id": "planner.task-surface",
  "fragment_version": "0.1.0",
  "target_level": "DISCOVERY",
  "source": "LIVE_UI",
  "observed_at": "2026-08-08T16:00:00Z",
  "selector_observations": [
    {
      "selector_key": "task.list_container",
      "result": "UNIQUE_MATCH",
      "structural_digest": "sha256:<sanitized shape digest>"
    }
  ],
  "locale": "pt-PT",
  "ui_surface_signal_digest": "sha256:<optional UI signal digest>"
}
```

This skeleton is illustrative. It is not evidence and must never be copied as if a live observation had occurred.

## 3. Evaluate the observation

```text
python scripts/attest_ui_contract.py evaluate /secure/local/observation.json
```

Exit codes:

```text
0  PASSED
2  REVIEW_REQUIRED
3  FAILED
4  invalid input / operational error
```

Evaluation is fail closed on:

- contract-set digest mismatch;
- campaign identity mismatch;
- fragment version mismatch;
- missing, additional or reordered selector observations;
- non-live evidence when a live promotion would otherwise occur;
- selector ambiguity/no-match/structure mismatch;
- missing read probe for READ/MUTATION;
- missing mutation approval/read-back/compensation evidence.

## 4. Persist sanitized evidence metadata

Optional persistence uses the `CORE-018` store:

```text
python scripts/attest_ui_contract.py evaluate \
  /secure/local/observation.json \
  --state /var/lib/m365-ui-mcp/capability-evidence.db
```

Only the bounded `CapabilityEvidenceRecord` is persisted. The observation document itself is not copied into the state store.

The evidence digest is computed from the sanitized observation bundle. It is bound to the exact contract-set digest and exact fragment metadata.

## 5. Discovery workflow

When a selector has no declared typed locator plan:

```text
DISCOVERY live observation
        ↓
REVIEW_REQUIRED
        ↓
review sanitized structural evidence
        ↓
propose typed closed locator in UIContract
        ↓
normal PR + CI + review
        ↓
new contract-set digest
        ↓
run a fresh UI campaign against that exact digest
```

The tooling never derives a selector from a screenshot, raw DOM, model guess or arbitrary browser probing.

A contract change invalidates the old campaign identity by design.

## 6. UI attestation workflow

For `UI` evidence:

- every selector in the fragment must be observed exactly once and in contract order;
- every selector must resolve uniquely;
- every `UNIQUE_MATCH` carries a sanitized structural digest;
- a selector without a declared locator remains `REVIEW_REQUIRED`;
- an already attested fragment that contradicts the live observation becomes `DRIFTED`;
- an unattested contract is never promoted to `HEALTHY` merely because an observation file says it passed.

A reviewed contract attestation change may therefore require a fresh confirmation campaign against the new contract-set digest before persisted runtime evidence is `HEALTHY`.

## 7. READ attestation workflow

`READ` requires all UI conditions plus:

```text
read_probe_ok = true
```

The read probe must be semantic and structurally validated. Tenant content is not retained as evidence.

A missing or failed read probe is not support.

## 8. MUTATION attestation workflow

`MUTATION` is supported by the evaluator but is not permission to mutate a production tenant.

A mutation observation must satisfy all UI/READ conditions and additionally provide:

```text
approval_digest
mutation_applied = true
read_back_ok = true
compensation_proven = true
```

The approval value is an opaque SHA-256 digest, never an identity or raw approval payload.

A live mutation campaign may only be executed when all relevant later gates are satisfied, including browser/session hardening, controlled egress, policy/approval integration and an explicitly safe non-production target. If those conditions are not available, mutation attestation remains operationally blocked rather than simulated as live.

## 9. Drift handling

For an already attested fragment:

```text
NO_MATCH
AMBIGUOUS
STRUCTURE_MISMATCH
        ↓
FAILED
        ↓
DRIFTED
        ↓
capability-scoped refusal
        ↓
RE_ATTESTATION_REQUIRED
        ↓
fresh discovery/attestation campaign
```

For an unattested fragment, the same contradiction remains `RE_ATTESTATION_REQUIRED`; it does not create a false claim that previously supported live behavior drifted.

## 10. CI policy

CI may:

- generate deterministic campaigns;
- evaluate mock/sanitized fixture observations;
- validate parser/refusal behavior;
- verify that mock evidence cannot promote live state;
- test integration with the sanitized evidence store.

CI must never:

- authenticate to the corporate Microsoft 365 tenant;
- execute a real attestation campaign;
- approve MFA or bypass Conditional Access;
- perform a live mutation;
- capture authenticated screenshots/DOM/content.

## 11. Operational acceptance

`CORE-019` repository-side acceptance is satisfied when:

1. campaign identity is deterministic and digest-pinned;
2. observation input is closed and sanitized;
3. mock evidence cannot promote live state;
4. selector contradictions fail closed;
5. READ requires a semantic probe;
6. MUTATION requires approval, read-back and compensation evidence;
7. output integrates with `CORE-018` persistence;
8. the runbook is reproducible;
9. all CI/security/image/SBOM gates are GREEN.

Live Planner evidence is a separate operational gate. Until it is actually collected under the controlled browser/egress prerequisites, existing Planner fragments remain `UNVERIFIED_LIVE`.
