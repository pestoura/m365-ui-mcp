# Live Worker UI Attestation Probe — Implementation Plan

**Date:** 2026-08-15
**Branch:** `feat/live-worker-attestation-probe` (worktree, base `origin/main` `aad84d9`)
**Requirement ID:** UI-AUTH-001
**Design:** `docs/superpowers/specs/2026-08-15-live-worker-ui-attestation-design.md`

## 0. TDD contract

RED first: write `tests/test_live_attestation_probe.py` exercising the new
module + route and confirm it fails. Then implement. Then GREEN. Then static
gates + full suite.

## 1. Files to create

1. `src/m365_browser_worker/live_attestation_probe.py`
   * `PLANNER_SURFACE_FRAGMENT_IDS`
   * `LiveProbeError`
   * `async def probe_live_surface_fragment(browser, *, fragment_id) -> dict`
   * `async def probe_all_live_surface_fragments(browser) -> list[dict]`
   * canonical `_structural_digest`/`_selector_structural_shape` (value-free,
     identical shape to `attestation_collection`)
2. `src/m365_browser_worker/planner_surface_probe.py`
   * `probe_planner_surfaces(browser) -> dict` — aggregates the two fragments
3. `tests/test_live_attestation_probe.py`

## 2. Files to edit

1. `src/planner_browser_worker/app.py`
   * import the new helper + constants
   * add `GET /auth/bootstrap/probe-planner-surface` mirroring
     `/auth/bootstrap/collect-observation` (loopback, GET-only, no query,
     positive-broker precondition, sanitized 503/200).
2. (No contract JSON edits. Fragments stay UNVERIFIED_LIVE — no locator
   invention.)

## 3. Implementation steps (minimal)

### Step 1 — RED

Write `tests/test_live_attestation_probe.py` with:

* `test_fragment_allowlist_is_fixed` — asserts
  `PLANNER_SURFACE_FRAGMENT_IDS == ("planner.plan-surface", "planner.task-surface")`.
* `test_probe_rejects_unknown_fragment` — `_FakeBrowser` + unknown id →
  `LiveProbeError`.
* `test_probe_fails_closed_when_not_on_planner_surface` — started, dedicated,
  but `planner_web_surface_present() == False` → `LiveProbeError`.
* `test_probe_fails_closed_on_ambiguous_page_set` — two pages → `LiveProbeError`.
* `test_probe_reports_no_locator_for_unlocatable_selector` — fragment selectors
  have no `locators` plan → each selector reported `NO_LOCATOR`, aggregate
  `all_unique_match == False`. (Mirrors the real blocker.)
* `test_probe_unique_match_with_declared_locator` — `_FakePage` with a declared
  `locators` plan returning count==1 → `UNIQUE_MATCH` + `structural_digest`.
* `test_route_loopback_peer_accepted` — GET route 200 against loopback peer.
* `test_route_docker_network_peer_denied` — 404.
* `test_route_query_string_rejected` — 400.
* `test_route_not_on_planner_surface_fails_closed` — 503 sanitized.
* `test_route_no_new_post_route` — route is GET, passes
  `test_no_unapproved_mutating_routes` (GET only; no PUT/PATCH/DELETE).

Run `pytest tests/test_live_attestation_probe.py` → must be RED (import errors /
missing symbols).

### Step 2 — GREEN

Implement `live_attestation_probe.py` and `planner_surface_probe.py`, then the
route. Mirror `collect_observation.py` / `bootstrap_discovery.py`:

* inject async `live_probe` that reads `browser._context.pages[0]` and
  `build_locator(page, plan.primary).count()`.
* positive-broker precondition uses `browser.is_dedicated_persistent_profile()`,
  `browser.planner_web_surface_present()`, and `len(pages)==1`.
* load fragment via `load_ui_contract_set()`; check not `DRIFTED`; per selector
  parse `locator_plan_from_metadata`; `NO_LOCATOR` when absent.
* digest via the canonical shape builder.
* route returns `{ok, fragments:[...]}`; 503 sanitized on `LiveProbeError`.

Re-run targeted test → GREEN.

### Step 3 — static gates

```
python -m compileall -q src tests
ruff check .
mypy
python scripts/check_docs.py
python scripts/check_contracts.py
python scripts/check_no_secrets.py
python scripts/check_policy_metadata.py
python scripts/check_base_image_pinning.py
python -m pytest -q tests/test_live_attestation_probe.py
```

### Step 4 — full suite

`python -m pytest -q --import-mode=importlib` (background + poll; worktree
venv gotcha: use `PYTHONPATH=$PWD/src` because the shared venv resolves
`m365_mcp` to a different checkout). Confirm the only possible red is
`test_common_auth_attestation_matrix.py::test_matrix_3_common_and_planner_attested_gate_may_pass`;
verify it against clean `origin/main` and do NOT mask it.

## 4. Self-review checklist

* [ ] No second persistent context opened.
* [ ] No MCP tool / catalog entry / control-plane proxy.
* [ ] GET-only route; passes `test_no_unapproved_mutating_routes`.
* [ ] Socket-loopback admission; 404 for non-loopback; headers can't spoof.
* [ ] Output only IDs, digests, counts, UNIQUE_MATCH/NO_MATCH/AMBIGUOUS/NO_LOCATOR.
* [ ] No URL/DOM/text/value/token/identity leaves.
* [ ] Fail-closed on: non-loopback, query, unstarted, wrong profile, not on
  Planner surface, ambiguous page set, drift, locator error, unknown fragment.
* [ ] No selector invented; `NO_LOCATOR` honest when fragment has no `locators`.
* [ ] No fragment self-promotion; contracts unchanged.
* [ ] Operation name has no `goto`/`navigate` token.

## 5. Deploy (preserve volume/profile)

Like-for-like recreate of `planner-mcp-browser-worker-1` from merged `main`
(`references/controlled_redeploy_source_only.md`): build
`planner-browser-worker:0.1.0`, tag pre-change rollback, `docker stop && rm`
then `docker run -d` with the EXACT same flags (name, networks
`planner-mcp_browser-internal` + `planner-mcp_m365-egress`, `-p 127.0.0.1:8090:8090`,
volume `planner-mcp_browser-profile`, env `PLANNER_MODE=live M365_MODE=live …`).
Do NOT publish 8090 to `0.0.0.0`.

Fresh-confirm post-deploy (read-only, no navigate/login):
`GET /auth/session` → broker `viable=true`, `auth_state=AUTHENTICATED`,
`account_context.state=VERIFIED`, `valid=true`. If the session does not recover
and MFA is required, STOP at that point.

## 6. Live probe + smoke

Run `GET /auth/bootstrap/probe-planner-surface` from inside the container
(loopback peer). Report per fragment: `NO_LOCATOR` (real blocker) or
`UNIQUE_MATCH`+digest. Follow canonical evidence→attestation→PR/CI→merge→deploy
only if typed locators are legitimately declared; otherwise stop with the exact
technical blocker.

Then read-only MCP smoke: `health`, `readiness`, `auth_session_info`,
`ui_contract_status`, `smoke_test`, `account_context`, `license_capabilities`,
`plan_list` and `task_list` (if a plan id is known). Zero mutations.
