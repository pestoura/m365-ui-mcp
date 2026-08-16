# Planner structural locator inspector — design specification

Status: SPECIFICATION-ONLY. No code, tests, endpoints, locators, attestation,
deployment, auth, MFA, browser navigation, Docker changes, or M365 mutations are
defined here. This document authorizes a controlled design and a dedicated ADR;
it does not implement anything.

Spec ID: `SPEC-M365-INSPECT-2026-08-16`
Date: 2026-08-16
Canonical repo: `pestoura/m365-ui-mcp`
Derived from: `CORE-019` (docs/m365-transition/roadmap-and-backlog.md),
runbook `RB-M365-UI-ATTEST-001` (docs/m365-transition/runbooks/ui-attestation.md),
`docs/ui-contract.md` (UI-xxx), `docs/privacy-boundary.md` (PRIV-xxx),
`docs/authentication-and-mfa.md` (AUTH-xxx), `docs/browser-worker.md` (WORKER-xxx),
ADR-001, ADR-002, ADR-006, ADR-007, ADR-008.

Related requirement anchors:

- `UI-002` — selectors are never invented; a locator is written only after a
  recorded live observation.
- `UI-004` — selectors/XPaths/CSS/DOM fragments are never caller-supplied and
  never returned through the public surface.
- `UI-071` — no raw DOM export; attestation may record a structural digest with
  text and attribute values stripped.
- `PRIV-064` — no authenticated screenshots.
- `AUTH-023` / `AUTH-030` — `AUTHENTICATED` requires a valid session probe plus a
  matching `AccountContext` (state `VERIFIED`, `professional=true`,
  `expected_profile=true`).
- `ADR-002` — generic browser primitives are not exposed as public MCP tools;
  the worker accepts only closed typed operation envelopes.
- `ADR-007` — only the dedicated persistent professional Chromium profile is used.

---

## 1. Problem statement

The live in-process Playwright probe against the already-running `planner-browser-worker`
proves the prerequisite platform state:

- `broker_viable = true`;
- `account_context.valid = true` (state `VERIFIED`, `professional=true`,
  `expected_profile=true`);
- `planner_web_surface_present = true`;
- exactly one page is open on the Planner Web surface.

The probe resolves the seven fixed selector keys
(`plan.list_container`, `plan.list_item`, `plan.title`, `task.list_container`,
`task.list_item`, `task.title`, `task.bucket`) to their declared plan contracts,
but those plans have no locator strategy values yet. The probe therefore returns
`NO_LOCATOR` for all seven keys: the UIContract fragments are at
`UNVERIFIED_LIVE` (per `RB-M365-UI-ATTEST-001` discovery stage), not drift.

The blocker is the discovery gap, not a runtime defect: `planner_plan_list`,
`planner_plan_get`, `planner_task_list`, `planner_task_get`, `planner_project_snapshot`
and `planner_smoke_test` cannot advance to `UI_ATTESTED`/`READ_ATTESTED` because the
structural locators that must back their `ui_contract_dependencies` have never been
observed and authored.

`CORE-019` forbids fabricating selectors and forbids a generic browser executor.
But `CORE-019` also requires a deterministic discovery workflow that produces
sanitized structural evidence for a later reviewed PR. The missing piece is an
**operator-only, local-only, closed structural inspector** that can read the
already-running worker Playwright context and emit sanitized candidate structural
representations for the seven fixed keys — without becoming a generic DOM crawler
and without ever reaching the public MCP surface.

This spec defines that inspector as a narrow `CORE-019` carve-out.

---

## 2. Non-goals

The inspector does NOT:

- implement any capability, endpoint, tool, locator plan, attestation, or contract edit;
- perform M365 mutations, clicks, typing, navigation, or page changes of any kind;
- open a second persistent Chromium context, profile, or user-data directory;
- accept caller-supplied input of any kind (no selector, CSS, XPath, JS, URL, text
  query, plan title, plan id, task id, or arbitrary attribute name);
- return raw DOM, page text, href/URL values, cookies, tokens, UPN/account identity,
  plan/task names, descriptions, or user-content identifiers;
- screenshot the authenticated UI (`PRIV-064`);
- promote, self-attest, or modify `contracts/ui_contract.json` or any fragment;
- expose anything over the MCP surface, an HTTP route, a Docker port, or Cloudflare;
- use Microsoft Graph;
- hard-code, filter on, or scope to the title "UCS – Segurança Técnica", or to any
  plan title / plan id / task id.

---

## 3. Invariants and security boundaries

These are hard constraints. The inspector MUST fail closed if any is violated.

- `I-1` Operator-only and local-only. The inspector is reachable only from the
  operator's host, in `live` mode, against the running worker process. It is never
  registered as an MCP tool and never published as an HTTP endpoint
  (ADR-002, `UI-004`).
- `I-2` Reuse the running context. It operates on the already-started worker
  Playwright `Browser`/`Page` only. No second persistent profile copy
  (ADR-007, `PRIV-030`).
- `I-3` No caller-supplied expression. Input vocabulary is the fixed seven selector
  keys and the fixed attribute allowlist below. Anything else is rejected without
  inspection (`UI-004`).
- `I-4` Closed structural signal allowlist. Only allowlisted safe structural
  attributes may be read (Section 6). No arbitrary attribute name is ever read.
- `I-5` Sanitized output only. Output contains fixed `selector_key`, allowlisted
  structural candidates with value-free/value-bounded representation, match
  count/cardinality, and a controlled evidence digest. No tenant content, identity,
  or URL.
- `I-6` Fail closed. Ambiguity, unsupported attribute, wrong origin, wrong page
  count, `broker_viable != true`, `account_context.valid != true`, or
  `planner_web_surface_present != true` abort the run with a typed error and no
  partial DOM exposure.
- `I-7` Read-only. The inspector performs only queries. It never dispatches a
  mutation, a click, a navigation, or a write to the page, the contract, or the
  profile.
- `I-8` No self-promotion. Evidence produced here does not change attestation state.
  Promotion follows the normal reviewed PR + CI path (`RB-M365-UI-ATTEST-001` §5).

---

## 4. Why this is a controlled CORE-019 exception

`CORE-019` is "Attestation tooling/runbook — deterministic discovery/attestation
workflow, never CI against real tenant". Its runbook already defines an
operator-only collection script (`scripts/collect_live_attestation_observation.py`)
that outputs only campaign/fragment metadata and normalized structural SHA-256 digests,
binds to `contract_set_digest`, and "NEVER marks a contract ATTESTED and NEVER edits
source contract JSON".

The inspector is the structural-authoring leg of that same discovery stage. It is an
exception only in the narrow sense that it reads the still-open live page to produce
*allowlisted structural candidates* for the seven keys, instead of relying on an
operator eyeballing a screenshot (which `PRIV-064` forbids). It stays inside `CORE-019`
because it:

- is operator-only and local-only (`I-1`);
- accepts no caller-supplied browser expression (`I-3`, satisfying `UI-004`);
- emits only sanitized structural signals (`I-5`), matching the runbook's
  "structural_digest / UNIQUE_MATCH" evidence shape;
- never promotes attestation (`I-8`).

It is explicitly NOT a relaxation of ADR-002 (generic browser primitives stay out of
the public MCP surface) and NOT a relaxation of `UI-002` (locators are still authored
by a human reviewer from this evidence, then re-observed under a fresh campaign digest).

A dedicated ADR — `ADR-009 — Operator-only structural locator inspector (CORE-019
discovery carve-out)` — MUST be written during implementation/planning to record this
exception, its boundaries, and its enforcement. This spec does not implement that ADR.

---

## 5. Architecture and components

The inspector is a single host-side, operator-invoked component that shares the worker
process address space / Playwright context. It is NOT a new service, NOT a container,
and NOT an exposed port.

Components:

- `InspectorRequest` — closed input. Exactly one field: an ordered subset (or all)
  of the seven fixed `selector_key` values. No other field exists.
- `StructuralSignalReader` — reads only allowlisted structural attributes from the
  already-loaded `Page` for a given `selector_key` scope, using fixed internal
  anchors (Section 6). It performs no navigation.
- `CandidateCanonicalizer` — reduces each observed element to a value-free/value-bounded
  structural candidate (Section 6) and computes a controlled evidence digest.
- `AdmissionGate` — enforces Section 8 preconditions and fails closed.
- `InspectorReport` — the sanitized output (Section 7).

Trust boundary: same as `ADR-002` worker zone. The inspector has no public route and
no MCP registration. It is invoked by the operator from the host, in-process with the
worker, never via the control plane or the public MCP.

Discovery scope is fixed to the seven keys. The inspector has no concept of "plan
title", "task title content", or any other user-visible string; strings such as
"UCS – Segurança Técnica" are never inputs, selectors, filters, or outputs.

---

## 6. Fixed selector and attribute allowlists

### 6.1 Selector keys (closed, exactly seven)

```
plan.list_container
plan.list_item
plan.title
task.list_container
task.list_item
task.title
task.bucket
```

Any `selector_key` outside this set is rejected at admission (`I-3`).

### 6.2 Attribute allowlist (closed, safe structural signals only)

For each matched element the reader may observe ONLY these structural signals:

| Signal | Allowed representation | Notes |
| --- | --- | --- |
| `tag` | lowercase tag name string | e.g. `div` |
| `role` | ARIA `role` value if present | value-bounded by observed set |
| `data_automation_id` | presence + opaque digest, NOT raw value | observed `data-automation-id` |
| `data_testid` | presence + opaque digest, NOT raw value | observed `data-testid` |
| `structural_index` | integer position within parent/scope | bounded, 0-based |
| `sibling_count` | integer cardinality of the scope | bounded |
| `depth` | integer DOM depth from a fixed anchor | bounded |

Prohibited reads (non-exhaustive, enforced by allowlist, not by blocklist):
`href`, `src`, any URL, `textContent`/`innerText`, any `class` value beyond a
structural digest, `id` beyond a digest, `style`, `title`, `aria-label` raw value,
`cookie`, `token`, `upn`, `email`, any attribute whose name is caller-supplied.

Rationale: every allowlisted signal is structural and value-free or value-bounded.
None exposes tenant content, identity, or navigation target (`UI-071`, `PRIV-064`,
`AUTH-032`).

### 6.3 Candidate canonical form

A structural candidate is:

```
{
  "selector_key": <one of the seven>,
  "tag": <string>,
  "role": <string|null>,
  "has_data_automation_id": <bool>,
  "data_automation_id_digest": <"sha256:<hex>"> | null,
  "has_data_testid": <bool>,
  "data_testid_digest": <"sha256:<hex>"> | null,
  "structural_index": <int>,
  "sibling_count": <int>,
  "depth": <int>
}
```

Raw attribute values are never present. Where a digest is required, it is computed
over the raw attribute value at capture time and the raw value is discarded
(`PRIV-062` redaction at write time).

---

## 7. Sanitized output schema

`InspectorReport`:

```
{
  "spec_id": "SPEC-M365-INSPECT-2026-08-16",
  "contract_set_digest": "sha256:<hex>",
  "observed_at": "<RFC3339 UTC>",
  "mode": "live",
  "preconditions": {
    "broker_viable": true,
    "account_context_valid": true,
    "account_context_state": "VERIFIED",
    "professional": true,
    "expected_profile": true,
    "page_count": 1,
    "planner_web_surface_present": true
  },
  "selector_reports": [
    {
      "selector_key": <one of seven>,
      "result": "UNIQUE_MATCH" | "NO_MATCH" | "AMBIGUOUS" | "STRUCTURE_MISMATCH",
      "match_count": <int>,
      "candidates": [ <candidate canonical form> ],
      "evidence_digest": "sha256:<hex of sanitized candidates>"
    }
  ],
  "evidence_digest": "sha256:<hex of whole sanitized report minus volatile fields>"
}
```

Rules:

- `result` uses the same closed vocabulary as `RB-M365-UI-ATTEST-001` §2
  (`UNIQUE_MATCH`, `NO_MATCH`, `AMBIGUOUS`, `STRUCTURE_MISMATCH`).
- `UNIQUE_MATCH` requires exactly one candidate and a non-null `evidence_digest`.
- `AMBIGUOUS` carries the observed `match_count` and the sanitized candidates, but
  the inspector does NOT pick one; disambiguation is a human contract decision.
- No plan title, task title, URL, identity, or page text appears anywhere.
- `contract_set_digest` binds the evidence to the exact UIContractSet, so a later
  reviewed locator change invalidates the observation identity by design
  (`RB-M365-UI-ATTEST-001` §5).

---

## 8. Admission and fail-closed behavior

The inspector runs ONLY when ALL preconditions hold; otherwise it returns a typed
error and performs no DOM read beyond the minimal gate probe:

| Precondition | Source | Fail-closed error |
| --- | --- | --- |
| mode == `live` | config | `INSPECTOR_MODE_NOT_LIVE` |
| `broker_viable == true` | worker broker | `INSPECTOR_BROKER_NOT_VIABLE` |
| `account_context.valid == true` (state `VERIFIED`, `professional`, `expected_profile`) | `AccountContext` | `INSPECTOR_ACCOUNT_CONTEXT_INVALID` |
| exactly one page open | worker page registry | `INSPECTOR_PAGE_COUNT_INVALID` |
| page on `planner.cloud.microsoft` Planner Web surface | `planner_web_surface_present` | `INSPECTOR_WRONG_SURFACE` |
| all requested keys ∈ seven-key allowlist | Section 6.1 | `INSPECTOR_UNKNOWN_SELECTOR_KEY` |
| no caller-supplied expression present | Section 3 `I-3` | `INSPECTOR_CALLER_EXPRESSION_REJECTED` |

On any failure the report is limited to `{error, precondition_snapshot}` with no
candidates, no DOM, no text. The error never leaks identity, URL, or content.

---

## 9. Genericity across all plans

The inspector is structurally generic. It scopes only to the seven fixed selector
keys and to the Planner Web surface, never to a plan title or plan id. It operates on
whatever plans/tasks the authenticated account can see; it cannot enumerate, filter,
or favor any specific plan.

"UCS – Segurança Técnica" is NOT a locator, route, or scope anywhere in this design.
After implementation, the acceptance path uses `planner_plan_list` to return ALL
visible plans generically; the exact title string is matched ONLY in the returned
data to pick the acceptance fixture's `plan_id`. That plan id is then passed to
`planner_plan_get`, `planner_task_list`, a real `task_id` to `planner_task_get`,
`planner_project_snapshot`, and `planner_smoke_test` — all read-only, zero mutations.
The inspector's evidence feeds the locator authoring for the seven keys; the product
remains title-agnostic.

---

## 10. Evidence-to-locator authoring flow

1. Operator invokes the inspector locally against the running worker (`I-1`).
2. Admission gate passes (Section 8); inspector reads allowlisted structural signals
   for the seven keys from the live page (Section 6).
3. Inspector emits `InspectorReport` (Section 7) — sanitized, digest-pinned, no
   self-promotion (`I-8`).
4. Human reviewer reads the sanitized candidates and authors a typed closed locator
   plan per key into the UIContract fragment, choosing stable strategies in `UI-020`
   preference order (role+structure first; stable `data-automation-id` only when
   genuinely present).
5. The fragment JSON change goes through a normal PR + CI (`UI-006`, `GOV-040`).
6. The contract change yields a new `contract_set_digest`, invalidating the old
   campaign identity (`RB-M365-UI-ATTEST-001` §5).
7. A fresh `CORE-019` UI campaign runs against the new digest; selectors must resolve
   `UNIQUE_MATCH` with a structural digest before `UI_ATTESTED`/`READ_ATTESTED`.
8. Only then do `planner_plan_list` and dependents advance; acceptance uses the
   generic plan list + exact-title fixture match (Section 9).

The inspector never performs steps 4–7. It stops at step 3.

---

## 11. UIContract / attestation integration

- The inspector output shape aligns with `RB-M365-UI-ATTEST-001` §2
  (`selector_observations`: `selector_key`, `result`, `structural_digest`). The
  `InspectorReport.evidence_digest` is the per-key `structural_digest` input the
  evaluator already consumes.
- Locator authoring respects `UI-020`..`UI-025` (preference order, forbidden
  strategies, fallback cap of three, ambiguity rule, zero-match rule, bounded wait).
- `UI-002` is preserved: the authored locator is an observation-derived proposal, not
  an invented value. The inspector supplies the observation; the reviewer supplies
  the authored, attested fragment.
- `UI-004` is preserved: no caller-supplied selector reaches the contract; the
  inspector's inputs are the closed seven-key set, not caller text.
- Promotion remains the reviewed PR + CI path; the inspector has no write path to
  `contracts/`.

---

## 12. Error cases

| Error | Trigger | DOM exposure |
| --- | --- | --- |
| `INSPECTOR_MODE_NOT_LIVE` | mode != live | none |
| `INSPECTOR_BROKER_NOT_VIABLE` | broker_viable != true | none |
| `INSPECTOR_ACCOUNT_CONTEXT_INVALID` | account_context.valid != true | none |
| `INSPECTOR_PAGE_COUNT_INVALID` | page_count != 1 | none |
| `INSPECTOR_WRONG_SURFACE` | not Planner Web surface | none |
| `INSPECTOR_UNKNOWN_SELECTOR_KEY` | key outside seven-set | none |
| `INSPECTOR_CALLER_EXPRESSION_REJECTED` | any caller-supplied expression | none |
| `INSPECTOR_AMBIGUOUS` | >1 candidate for a key | sanitized candidates only, no pick |
| `INSPECTOR_NO_MATCH` | 0 candidates for a key | none |
| `INSPECTOR_STRUCTURE_MISMATCH` | anchor/structure contradiction | sanitized shape only |

All errors are value-free of tenant content and identity.

---

## 13. Audit, logging, and redaction

- Audit events record only: `spec_id`, `contract_set_digest`, `observed_at`,
  `preconditions` booleans/states (no identity), per-key `result` and `match_count`,
  and the `evidence_digest`.
- No cookies, tokens, URLs, page text, plan/task names, UPN, tenant GUID, or profile
  path is logged (`PRIV-062`, `PRIV-063`).
- Redaction happens at capture time: raw attribute values are digested and dropped
  before any report or log line is constructed (`UI-071`, `PRIV-062`).
- Audit entries are append-only and bounded-retention per `PRIV-060`.

---

## 14. Testing strategy (specification of intent; no code here)

- `T-1` Admission rejects each precondition failure with the correct typed error and
  zero DOM exposure (mock `AccountContext` / broker / page registry).
- `T-2` Attribute allowlist test: a mock DOM with disallowed attributes yields no
  leaked value; only allowlisted signals appear.
- `T-3` Sanitization test: a mock page containing plan/task titles, URLs, and UPN
  produces a report with none of them present.
- `T-4` Ambiguity test: >1 candidate yields `AMBIGUOUS` with `match_count` and
  sanitized candidates, and the inspector chooses none.
- `T-5` Zero-match test: 0 candidates yields `NO_MATCH`, no fabricated locator.
- `T-6` Digest-pinning test: identical sanitized input yields stable `evidence_digest`;
  a contract-set change yields a different campaign identity (mirrors
  `RB-M365-UI-ATTEST-001` §5).
- `T-7` Genericity test: the inspector behavior is invariant to plan title/id; a
  fixture titled "UCS – Segurança Técnica" and one titled anything else produce
  identical structural candidate shapes for the seven keys.
- `T-8` No-public-surface test: CI asserts the inspector is not registered as an MCP
  tool and exposes no HTTP route (extends `UI-091` boundary assertion).
- `T-9` No-self-promotion test: invoking the inspector never changes fragment
  `support_state` or `attestation` (extends `UI-006` governance).

---

## 15. Rollout and rollback

Rollout:

- Ship the spec + `ADR-009` first (this document is the spec half).
- Implement the inspector as operator-only/local-only behind the admission gate.
- Keep `contracts/ui_contract.json` unchanged until a reviewed locator PR lands.
- Discovery evidence is collected, reviewed, and promoted only through `CORE-019`.

Rollback:

- The inspector is additive and side-effect-free. Disabling it (remove the
  operator entrypoint) leaves runtime behavior unchanged; the seven keys remain
  `UNVERIFIED_LIVE` and the probe continues to return `NO_LOCATOR` until a reviewed
  locator lands.
- No contract, Docker, auth, or MCP change is required to roll back, because the
  inspector writes nothing.

---

## 16. Acceptance criteria

After implementation (not part of this spec's scope):

- `AC-1` The inspector runs only under the Section 8 preconditions; otherwise it
  fails closed with a typed error and no DOM exposure.
- `AC-2` `planner_plan_list` returns ALL plans visible to the authenticated account
  generically, with no title-based filtering or scoping.
- `AC-3` The exact title "UCS – Segurança Técnica" is located ONLY by matching the
  returned `plan` data, and its returned `plan_id` is used for the dependent reads.
- `AC-4` `planner_plan_get`, `planner_task_list`, a real returned `task_id` for
  `planner_task_get`, `planner_project_snapshot`, and `planner_smoke_test` all succeed
  read-only with zero mutations.
- `AC-5` The seven selector keys resolve `UNIQUE_MATCH` with a structural digest under
  a fresh `contract_set_digest` campaign before their fragments advance past
  `UNVERIFIED_LIVE`.
- `AC-6` The inspector is confirmed absent from the public MCP tool catalogue and
  from any HTTP route.
- `AC-7` Audit/evidence contains no tenant content, identity, URL, or screenshot.

---

## 17. Explicit statement: UCS is only an acceptance fixture

"UCS – Segurança Técnica" is an acceptance-only fixture. It is NEVER a locator,
selector, route filter, product scope, or structural anchor in this design or in the
inspector. The product and the inspector remain generic across all Planner plans and
tasks visible to the authenticated account. The title string appears in the acceptance
path solely as an exact-match over `planner_plan_list` output to select the fixture
`plan_id` for the read-only demonstration in `AC-3`/`AC-4`.
