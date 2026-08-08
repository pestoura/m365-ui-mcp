# Testing Strategy

Scope: the test pyramid for `pestoura/planner-mcp` (control plane) and `planner-browser-worker`. Companions: [acceptance.md](acceptance.md), [ui-contract.md](ui-contract.md), [browser-worker.md](browser-worker.md), [release-process.md](release-process.md), [observability.md](observability.md).

## 0. Non-negotiable rule

**CI never touches a live Microsoft Planner tenant.** No CI job may authenticate to Planner, open a real Planner URL, or mutate real data. All browser-level testing in CI runs against the **mock Planner UI** fixture server. Live verification is a separate, manual, human-initiated procedure, read-only in its initial phase, documented in [acceptance.md](acceptance.md).

Enforcement:

| Control | Mechanism |
|---------|-----------|
| Network egress | CI test job runs with egress denied except to `127.0.0.1` and the package proxy. |
| Env guard | `PLANNER_ENV` is pinned to `ci`; the worker refuses to start with `env=live` when `CI=true`. |
| Credential absence | No Planner secrets exist in CI secret scope; a repo policy test asserts the secret names are unset. |
| URL allowlist | Worker navigation allowlist in `ci` mode is `http://127.0.0.1:*` only; any other host raises `WRK_NAV_BLOCKED`. |
| Static check | Grep gate fails the build on `tasks.office.com`, `planner.cloud.microsoft` or `login.microsoftonline.com` literals outside `docs/` and the allowlist module. |

## 1. Layers

| Layer | Runtime | Runs in CI | Touches browser | Touches live Planner | Typical count |
|-------|---------|-----------|-----------------|----------------------|---------------|
| L1 Unit | pytest | yes | no | no | ~400 |
| L2 Schema | pytest + JSON Schema | yes | no | no | ~90 |
| L3 Contract | pytest + FastMCP/HTTP clients | yes | no | no | ~120 |
| L4 Mock-UI (Playwright) | pytest-playwright | yes | yes (headless, local mock) | no | ~70 |
| L5 Selector attestation | pytest | yes (structural) / manual (live) | yes | read-only, manual only | ~1 per selector |
| L6 Isolated acceptance | scripted, compose-based | nightly + pre-release | yes | no | ~25 scenarios |
| L7 Live acceptance | manual, human-operated | never | yes | read-only first | checklist |

## 2. L1 — Unit tests

Targets: pure logic with no I/O.

| Area | Representative assertions |
|------|---------------------------|
| Idempotency keys | Key derivation is stable under field reordering; differing intent yields differing key. See [idempotency.md](idempotency.md). |
| State model | Normalization of Planner Premium fields; unknown field handling is lossless-or-explicit. |
| Reconciliation | Drift classification (`missing`, `extra`, `divergent`, `equivalent`) is total and mutually exclusive. |
| Redaction | Every detector class from [observability.md](observability.md) has positive and negative cases. |
| Policy | Read-only mode denies all mutating tools; dry-run never reaches the worker client. |
| Retry | Backoff is bounded, jittered, and never retries non-retryable error codes. |
| Graph contextual client | Any Graph failure degrades to `available=false` and returns success from the caller's perspective. |

Rules: no `sleep`, no network, no filesystem outside `tmp_path`, deterministic clock via injected `Clock`, deterministic ULIDs via injected id factory.

## 3. L2 — Schema tests

Artifacts under version control: MCP tool input/output schemas, worker HTTP request/response schemas, audit row schema, sanitized MFA event schema, evidence bundle manifest schema.

| Assertion | Rationale |
|-----------|-----------|
| Every tool in [tool-catalog.md](tool-catalog.md) has a registered schema and vice versa. | No undocumented surface. |
| Schemas validate all recorded fixtures. | Fixtures stay in sync. |
| Backward-compat check against the previous release's schemas. | Additive-only changes unless a major bump. |
| Sanitized MFA event schema has `additionalProperties: false` and exactly the permitted fields (`operation_id`, `service`, `description`, `mfa_number`, `expires_at`). | Privacy boundary, see [privacy-boundary.md](privacy-boundary.md). |
| Audit `effect` never contains raw values, only hashes and field names. | Evidence without leakage. |

## 4. L3 — Contract tests

Two contracts are exercised in-process with real serialization:

**Control plane ↔ MCP client.** Streamable HTTP transport, tool discovery, argument validation errors, `dry_run` semantics, idempotency replay, error taxonomy mapping, and denial reasons.

**Control plane ↔ browser worker.** The worker is replaced by a *contract double* generated from the same schema set; the real worker is separately verified against the same suite (dual-run contract testing), so drift between double and implementation is impossible to hide.

| Scenario | Expected |
|----------|----------|
| Duplicate `idempotency_key`, identical intent | Single worker call, `outcome=replayed`. |
| Duplicate key, divergent intent | `outcome=conflict`, no worker call. |
| Worker returns `read_back` mismatch | Tool returns `failed`, audit row records mismatch fields. |
| Worker unavailable | Tool returns retryable error; no partial audit `ok`. |
| Graph unavailable | Tool still returns `ok`; `graph.available=false`. |
| Unsupported premium capability | `denied` with `reason=unsupported_premium`, referencing [planner-premium-capabilities.md](planner-premium-capabilities.md). |

## 5. L4 — Mock Planner UI tests

The mock UI is a self-contained static+API application served on loopback that reproduces the DOM structure, ARIA roles, and interaction timing characteristics of the Planner Premium surfaces described in [ui-contract.md](ui-contract.md): board, grid, timeline, task detail pane, login/MFA interstitial.

| Property | Requirement |
|----------|-------------|
| Fidelity source | Every mock DOM node's structural contract is derived from a captured, sanitized snapshot stored under `tests/fixtures/ui/`. |
| Sanitization | Snapshots contain no tenant data: names, ids and text are replaced by synthetic values at capture time. |
| Determinism | No animation, fixed timers, seeded data. |
| Failure modes | Mock can be driven into: slow render, stale element, selector removed, extra modal, session expiry, MFA challenge. |

Mock-UI suites cover: navigation across surfaces, create/update/complete task, bucket moves, checklist edits, premium field edits, read-back verification, error recovery, and session-expiry handling.

Explicit boundary: passing L4 proves the worker's *logic* is correct against the contract. It does **not** prove the real Planner UI matches the contract — that is L5/L7's job, and no release note may claim live support on L4 evidence alone.

## 6. L5 — Selector attestation tests

Every logical selector in the UI contract registry (`selector_id` → strategy chain) is attested.

| Sub-layer | Where | What it proves |
|-----------|-------|----------------|
| A. Registry integrity | CI | Every `selector_id` used in code exists in the registry; no raw selector strings outside the registry; each entry has a primary strategy, ≥1 fallback, and an owner. |
| B. Mock attestation | CI | Each selector resolves to exactly one node in the mock UI, and each fallback also resolves. |
| C. Semantic attestation | CI | Resolved node satisfies its declared role/label/interactivity assertion (not merely "exists"). |
| D. Live attestation | Manual, read-only | A human-run session resolves each selector against the real Planner UI and records hit/fallback/miss into an attestation report. |

Attestation report format (`evidence/selectors/<date>-<env>.json`):

```json
{
  "captured_at": "2026-08-08T10:00:00Z",
  "env": "live-readonly",
  "app_build_hint": "planner-web-<sanitized>",
  "results": [
    {"selector_id": "task.detail.due_date", "outcome": "hit", "strategy": "primary", "role_ok": true}
  ],
  "summary": {"hit": 118, "fallback": 2, "miss": 0}
}
```

Release gate: a live attestation report with `miss == 0` is required before any documentation claims live Planner support (see [release-process.md](release-process.md)). Any `miss` freezes mutating tools.

## 7. L6 — Isolated acceptance

Runs the full compose topology from [deployment.md](deployment.md) — control plane, worker, mock UI — with real transports, real Playwright/Chromium, real persistence, no live tenant. Procedure and evidence formats are specified in [acceptance.md](acceptance.md).

Characteristics: fresh volumes per run, seeded mock dataset, scenario scripts driving MCP tools exactly as ChatGPT would through the Portal, and full evidence capture (logs, audit export, metrics snapshot, read-back diffs, optional screenshots).

## 8. L7 — Live acceptance

Manual only. Phase 1 is **read-only**: navigation, listing, reading tasks, selector attestation. Phase 2 (mutating) requires a dedicated non-production plan, explicit human approval per operation, and is never automated in CI. Full protocol in [acceptance.md](acceptance.md).

## 9. Fixtures

| Fixture set | Path | Content | Refresh policy |
|-------------|------|---------|----------------|
| UI snapshots | `tests/fixtures/ui/` | Sanitized DOM structure per surface | Manual, on observed UI change; sanitization test must pass |
| Tool payloads | `tests/fixtures/tools/` | Request/response pairs per tool | Regenerated when schemas change |
| Worker traces | `tests/fixtures/worker/` | Recorded step sequences | Regenerated with mock UI updates |
| Audit rows | `tests/fixtures/audit/` | Golden audit exports | Golden-file diff |
| Log records | `tests/fixtures/logs/` | Records that must be fully redacted | Extended on every redaction bug |
| Seed dataset | `tests/fixtures/seed/planner_seed.json` | Plans/buckets/tasks/premium fields for the mock | Versioned with the mock UI |

Fixture rules: no real tenant data ever, sanitization asserted by test, every fixture referenced by at least one test (orphan-fixture check in CI), and golden files updated only via an explicit `--update-golden` run reviewed in the PR diff.

## 10. Quality gates

| Gate | Threshold |
|------|-----------|
| Unit + schema + contract | 100 % pass |
| Coverage (control plane) | ≥ 90 % lines, ≥ 85 % branches |
| Coverage (worker logic, excluding Playwright glue) | ≥ 85 % |
| Mock-UI suite | 100 % pass, zero flakes over 3 consecutive runs |
| Selector registry integrity | 100 % |
| Redaction suite | 100 %, no skips permitted |
| Isolated acceptance | 100 % of pre-release scenarios |
| Flake budget | Any test failing intermittently is quarantined within 24 h with an owning issue |

## 11. Determinism and flake control

Fixed seeds; injected clock; no wall-clock sleeps (event/poll helpers only); Playwright `expect` auto-waiting with explicit timeouts; each mock-UI test runs in an isolated browser context; retries disabled in CI so flakes surface rather than hide.

## 12. Backlog mapping

| Layer | Backlog keys |
|-------|--------------|
| Unit + schema harness | P-054, P-055 |
| Contract + dual-run doubles | P-056, P-057 |
| Mock Planner UI | P-058, P-059 |
| Selector attestation | P-060, P-069 |
| Isolated acceptance harness | P-071 |
| Live read-only protocol | P-073 |
