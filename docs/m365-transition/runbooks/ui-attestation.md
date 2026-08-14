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

At the start of `CORE-019`, the current fragments are (`common.auth` has since been
split into the two atomic authentication fragments per `AUTH-107`):

```text
common.auth.email
common.auth.password
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

## 10. Authentication bootstrap (pre-attestation, fail-closed)

`CORE-019` previously blocked the LIVE UIContract authentication bootstrap
deadlock: the full-contract `live_guard` required an attested UIContract before
*any* live operation, which also blocked `/auth/status`, `/auth/start` and
`/auth/resume`. Authentication could therefore never begin, so the live
attestation campaign (which needs an authenticated professional session) could
never be collected.

The bootstrap deadlock is resolved by a **narrowly-scoped authentication
bootstrap guard** that is the only sanctioned pre-attestation live path. It is
not a generic browser primitive and never weakens the Planner/Outlook controls.

### Guard scope

- Applies ONLY to `auth_status`, `auth_start`, `auth_resume`.
- May operate BEFORE the `common.auth.email`/`common.auth.password` fragments are attested, but ONLY when ALL of:
  - the worker process owns a started live browser;
  - the browser is the **dedicated persistent professional profile**
    (`M365_BROWSER_PROFILE_DIR`, resolved by `browser_runtime_settings()`);
  - the live context is on an **approved Microsoft authentication origin**
    (`login.microsoftonline.com`, `login.live.com`, `login.microsoft.com`,
    `account.microsoft.com`, `entra.microsoft.com`) or no page is open yet so
    bootstrap may begin navigation.
- Fails closed on wrong origin / wrong profile / browser-not-started.
- Once BOTH `common.auth` fragments are legitimately attested (PR/evidence based), the normal
  stricter full-contract behavior applies to the auth endpoints again.
- Returns only `{state, mode}`. It never exposes raw DOM, page text, URLs,
  cookies, tokens, UPN, tenant IDs, mailbox content, or arbitrary navigation.

### Safe bootstrap procedure (operator, on host)

1. Confirm the worker runs in `live` mode against the dedicated profile:
   ```text
   M365_MODE=live
   M365_BROWSER_PROFILE_DIR=/var/lib/planner-worker/profile   # dedicated professional profile
   M365_REQUIRE_UI_ATTESTATION=true
   ```
2. Start the worker. `/readyz` will report `UI_CONTRACT_UNATTESTED` and
   `AUTH_NOT_AUTHENTICATED` — this is expected pre-bootstrap.
3. Call the bootstrap endpoints only from the private worker network:
   ```text
   GET /auth/status      -> {state, mode:"live"}      (bootstrap guard allows)
   GET /auth/start      -> {state}                   (operator completes MFA in Authenticator)
   GET /auth/resume     -> {state}                   (after MFA approval)
   ```
   These succeed pre-attestation because the guard permits authentication
   bootstrap on the dedicated profile at an approved auth origin. They do NOT
   read or return any tenant content.
4. Keep `account/context`, `account/license`, and every `/planner/*` read
   blocked until the relevant UIContract fragment is legitimately attested. The
   full-contract `live_guard` still enforces this; the bootstrap guard does not
   widen it.
5. Collect sanitized live observations with the OPERATOR-ONLY script (never a
   public MCP tool, never an exposed HTTP endpoint). The two atomic
   authentication fragments are collected SEPARATELY, each on its own real live
   surface (`AUTH-107`): the email surface before `begin-email`, the password
   surface after it.
   ```text
   python scripts/collect_live_attestation_observation.py \
     --fragment common.auth.email \
     --level DISCOVERY \
     --out /secure/local/common.auth.email.observation.json

   python scripts/collect_live_attestation_observation.py \
     --fragment common.auth.password \
     --level DISCOVERY \
     --out /secure/local/common.auth.password.observation.json
   ```
   The script outputs ONLY campaign/fragment metadata and normalized structural
   SHA-256 digests / UNIQUE_MATCH results. It binds to the current
   full-set `contract_set_digest` (`AUTH-108`) and reuses the
   `attest_ui_contract.py` plan/evaluate
   schema. It NEVER marks a contract ATTESTED and NEVER edits source contract
   JSON. If Playwright or the dedicated live profile is unavailable, it refuses
   rather than fabricating evidence.
6. Review each observation, then evaluate it (repository-side, safe):
   ```text
   python scripts/attest_ui_contract.py evaluate /secure/local/common.auth.email.observation.json
   python scripts/attest_ui_contract.py evaluate /secure/local/common.auth.password.observation.json
   ```
7. Promote only through the normal PR + CI + review path, per fragment. A passing
   observation
   is not attestation by itself; the fragment JSON is updated in the reviewed
   change, not by the runtime or the collection script. The authentication gate
   opens only when BOTH atomic fragments are attested.

### Forbidden shortcuts

- Do NOT expose the collection script as an MCP tool or HTTP endpoint.
- Do NOT let CI authenticate to the tenant or run a live campaign.
- Do NOT add any runtime endpoint that writes/edits source contract JSON or
  self-promotes ATTESTED.
- Do NOT let mock mode produce promotion-grade evidence.

## 11. CI policy

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

## 12. Operational acceptance

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
