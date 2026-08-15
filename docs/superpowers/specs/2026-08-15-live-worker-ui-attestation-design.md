# Live Worker UI Attestation Probe — Design

**Date:** 2026-08-15
**Author:** Jarvas (per approved user decision)
**Status:** Approved design, ready for TDD implementation
**Requirement ID:** UI-AUTH-001

## 1. Purpose

Collect sanitized UI-attestation evidence for the `planner.plan-surface` and
`planner.task-surface` UIContract fragments by reusing the ALREADY-RUNNING
Playwright `browser._context` (the dedicated persistent professional profile),
without opening a second persistent Chromium context and without destroying the
already-authenticated Microsoft session.

The mechanism is operator-only, local-only, read-only. Its only external
evidence is: known fragment/selector IDs, fresh contract-set digests, match
counts, and the closed results `UNIQUE_MATCH` / `NO_MATCH` / `AMBIGUOUS`. It
never returns raw DOM text, page URLs, cookies, tokens, UPNs, tenant IDs, or
account identity. It never fabricates selectors or locators (CORE-019).

## 2. Approved constraints (from the user decision)

* Reuse the live `PersistentBrowser._context` / page. No second persistent
  context. No profile/volume/state destruction. No new login.
* Operator-only: expose as a socket-loopback-only HTTP GET endpoint, not an MCP
  tool, not in any catalog, never proxied by the control plane.
* Output sanitized with IDs known to the contract set, digests, counts and
  `UNIQUE_MATCH/NO_MATCH/AMBIGUOUS`. No page content or identity.
* Fail-closed mandatory: reject when the broker is not viable /
  AUTHENTICATED / VERIFIED, when not on the Planner Web surface, when the page
  set is ambiguous (multiple pages), on drift/stale, or when any selector does
  not resolve to exactly one match.
* No invented selectors: scope is strictly the fragment allowlist
  (`planner.plan-surface`, `planner.task-surface`). A real locator is used only
  when the fragment JSON already carries a `locators` plan; otherwise the probe
  reports the fragment as not observeable (honest blocker, no fabrication).
* Static gates + full suite must pass. The only known pre-existing red is
  `tests/test_common_auth_attestation_matrix.py::test_matrix_3_common_and_planner_attested_gate_may_pass`;
  if it appears it must be confirmed against clean `origin/main` and not masked.

## 3. Architecture (reuse, do not reimplement)

Mirror the proven `GET /auth/bootstrap/collect-observation` primitive
(AUTH-105):

* `src/m365_browser_worker/collect_observation.py` already reuses the live
  `_context` via an injected async `live_probe`. Its `live_probe` iterates
  `context.pages[0]` and calls `locator_runtime.build_locator(page, plan.primary).count()`
  — read-only, no wait, no interaction.
* `src/m365_mcp/attestation_collection.collect_structural_observation` maps a
  per-selector match count (0/1/>1) onto
  `SelectorObservation(result=NO_MATCH|UNIQUE_MATCH|AMBIGUOUS, structural_digest?)`.
* `src/m365_browser_worker/bootstrap_discovery.discover_key` is the per-selector
  fixed-scope discovery primitive; it loads the plan via
  `common_auth_locator_plan` (fail-closed key set) and counts the PRIMARY
  candidate only.

The new mechanism differs from AUTH-105 in three ways:

1. Scope is the Planner surface allowlist, not the four `common.auth` keys.
2. Fragment IDs are taken from an explicit `PLANNER_SURFACE_FRAGMENT_IDS`
   constant (no caller input).
3. A positive-broker precondition is enforced BEFORE any probe: the broker must
   be `viable=true`, `auth_state=AUTHENTICATED`, `account_context.state=VERIFIED`,
   and the dedicated profile must sit on the Planner Web surface
   (`browser.planner_web_surface_present()`). These are exactly the conditions
   already proven by the post-MFA broker promotion (AUTH-115) and they are the
   minimum that makes observing the Planner board legitimate. Drift/stale is
   detected via `load_status().attested` + `UIContractSet` selector `status`
   checks, and an ambiguous page set (≠1 page) fails closed.

## 4. Module design

### 4.1 `src/m365_browser_worker/live_attestation_probe.py` (new)

Reusable, importable, browser-free-of-Playwright-calls-itself builder.

* `PLANNER_SURFACE_FRAGMENT_IDS: tuple[str, ...]` — hard-coded
  `("planner.plan-surface", "planner.task-surface")`. No caller may supply.
* `LiveProbeError` — fail-closed error carrying only a sanitized `reason`
  category (no values/URLs/exception text).
* `async def probe_live_surface_fragment(browser, *, fragment_id) -> dict`
  — for one allowlisted fragment:
  * Validate `fragment_id in PLANNER_SURFACE_FRAGMENT_IDS` (else `LiveProbeError`).
  * Precondition: `browser.started`, `browser.is_dedicated_persistent_profile()`,
    `browser.planner_web_surface_present()` (positive Planner Web surface), and
    exactly one open page (`len(browser._context.pages) == 1`). Any failure →
    `LiveProbeError` (fail closed).
  * Load the fragment via `load_ui_contract_set()`; verify it exists, is not
    `DRIFTED`, and every selector `status` is `ATTESTED` (a fragment without
    locators stays UNVERIFIED_LIVE and is reported as not observeable — honest
    blocker, no fabricated locator).
  * For each selector: parse the plan with `locator_plan_from_metadata`; if no
    `locators` plan exists → record `NO_LOCATOR` (honest, not invented); else
    build the locator against the single live page and `count()` only. Map
    0 → `NO_MATCH`, 1 → `UNIQUE_MATCH` (+ value-free `structural_digest`),
    >1 → `AMBIGUOUS`. Exceptions → `LiveProbeError`.
  * Return a sanitized dict: `fragment_id`, `contract_set_digest`,
    `surface_present`, `page_count`, per-selector
    `{selector_key, result, structural_digest?}`, and an aggregate
    `all_unique_match` boolean.

The digest uses the SAME canonical shape builder as
`attestation_collection._structural_digest` so values match across the runtime
and operator collectors. No URL/DOM/value leaves the function.

### 4.2 `src/m365_browser_worker/planner_surface_probe.py` (thin endpoint helper)

Reuses `probe_live_surface_fragment` for each allowlisted fragment and aggregates
the results. This is the single in-container callable the HTTP route invokes.

### 4.3 `GET /auth/bootstrap/probe-planner-surface` (new route, `app.py`)

Mirrors `collect-observation` exactly:

* Socket-level loopback admission (`is_loopback_peer`); non-loopback → 404.
* GET only; query string rejected (400); no body.
* Operation name avoids `goto`/`navigate` (the `auth_bootstrap.py` grep tokens).
* Enforces the positive-broker precondition (fresh
  `live_account_context(browser)` + `live_auth_state()`-equivalent +
  `browser.planner_web_surface_present()`) — on failure 503 sanitized.
* Returns `{ok, fragments:[...]}` with sanitized per-fragment evidence only.
* Never adds a POST route (passes `test_no_unapproved_mutating_routes`).
* Never weakens the evaluator: it only COLLECTS sanitized evidence; it promotes
  nothing and writes no contract JSON.

## 5. Fail-closed matrix

| Condition | Behavior |
|---|---|
| Non-loopback peer | 404 |
| Query string present | 400 INVALID_REQUEST |
| Browser not started / wrong profile | 503 sanitized |
| Not on Planner Web surface (no positive surface) | 503 sanitized |
| Page set ≠ 1 (ambiguous) | 503 sanitized |
| Fragment drifted / stale | 503 sanitized |
| Selector has no `locators` plan | reported `NO_LOCATOR` (honest, no fabrication) |
| Selector count 0 | `NO_MATCH` |
| Selector count 1 | `UNIQUE_MATCH` + digest |
| Selector count >1 | `AMBIGUOUS` |
| Locator count error | 503 sanitized |

## 6. Non-goals / boundaries

* Does NOT open a second persistent Chromium context.
* Does NOT navigate, fill, click, evaluate scripts, or mutate Planner.
* Does NOT invent selectors or self-promote a fragment to ATTESTED. Promotion
  stays PR/evidence-based.
* Does NOT expose any DOM text / URL / cookie / token / identity.
* Does NOT add an MCP tool or appear in any catalog; never proxied by the
  control plane.

## 7. Known blocker (real, not a relaxation)

The live `planner.plan-surface` / `planner.task-surface` fragments currently ship
with `value:null` and NO `locators` plan (confirmed at
`contracts/ui_fragments/surfaces/planner-premium-web/plan.json` and `task.json`).
CORE-019 forbids inventing selectors, and the authenticated headless profile
does not render the Planner board DOM in this context. Therefore, against the
live board the probe will honestly report `NO_LOCATOR` per selector (the fragment
is not observeable). This is the same real blocker recorded in
`references/planner_surface_attestation_blocker.md`. The mechanism is
implemented, tested, and merged; only the evidence collection for these two
fragments is gated by the absence of declared locators. The canonical workflow
(evidence → attestation → PR/CI → merge → deploy) applies as soon as typed
locators are legitimately declared for these fragments.

## 8. Verification contract

* RED: new tests fail before the implementation exists.
* GREEN: implementation makes them pass; full suite green.
* Static gates: `compileall`, `ruff`, `mypy`, `check_docs`, `check_contracts`,
  `check_no_secrets`, `check_policy_metadata`, `check_base_image_pinning` all
  green.
* Live probe against `planner-mcp-browser-worker-1`: reports per-fragment
  `NO_LOCATOR` (honest blocker) OR, if locators are declared, `UNIQUE_MATCH`
  with digest. No content leakage.
* Post-deploy read-only MCP smoke confirms the broker remains
  viable/AUTHENTICATED/VERIFIED and every listed read tool returns without
  mutation.
