# M365 Core Execution Status

This file is the execution overlay for the `CORE-*` definitions in `../roadmap-and-backlog.md`. It records only completed/executing gates; the roadmap remains the canonical definition of scope and order.

## Phase 1 — Product identity and shared-core extraction

| Key | Status | Evidence / decision |
|---|---|---|
| CORE-001 | PASS | Product identity ADR accepted in PR #215; merged to `main` at `24da6de7a88e18e7cc6f11b0216d91d602136816`; post-merge docs `31241171203` and CI `31241171204` SUCCESS. |
| CORE-002 | PASS | Repository renamed to `pestoura/m365-ui-mcp`; PR #216 merged to `main` at `7af511c1612573d9fc3822e37fa375901c3ec162`; post-merge docs `31241960632` and CI `31241960631` SUCCESS. |
| CORE-003 | PASS | Canonical namespaces/entry points; PR #217 merged to `09df4d3f1db9a370256dfd696b73c1a8e732881c`; post-merge docs `31242437571` and CI `31242437576` SUCCESS. |
| CORE-004 | PASS | Canonical `M365_*` with bounded historical aliases; PR #218 merged to `71d55d7c83f75e15808480081e214659c77dd8a1`; post-merge docs `31242924851` and CI `31242924852` SUCCESS. |
| CORE-005 | PASS | Generic control plane; PR #219 merged to `d7cd92c48258250248c53e2fd63828835f28c52a`; post-merge docs `31243362589` and CI `31243590216` SUCCESS. |
| CORE-006 | PASS | Generic browser/profile boundary; PR #220 merged to `ccf91b1afa61c7181b48fa43b4acfcb87ff78f9f`; post-merge docs `31254342686` and CI `31254342688` SUCCESS. |
| CORE-007 | PASS | Closed Application Registry; PR #221 merged to `d8d46fe9782abc104e6fd5580e7a0c0d269f8cd8`; post-merge docs `31254742904` and CI `31254742912` SUCCESS. |
| CORE-008 | PASS | Canonical Tool Registry; PR #222 merged to `1a8f182db8727dcc83550a795a01d48a49e120a2`; post-merge docs `31255232889` and CI `31255232909` SUCCESS. |
| CORE-009 | PASS | Metadata-driven semantic registration; PR #223 merged to `2c250af7763a325df34f53c826adea5c01e61a3d`; post-merge docs `31255688052` and CI `31255688039` SUCCESS. |
| CORE-010 | PASS | Bounded exposure profiles; PR #224 merged to `ccfb2c0382c1e812abad6517a5d735ddebe5ec62`; post-merge docs `31256189742` and CI `31256189728` SUCCESS. |

Phase 1 gate: **PASS / GREEN**.

## Phase 2 — Capability and UI contract redesign

| Key | Status | Evidence / decision |
|---|---|---|
| CORE-011 | PASS | Scoped Capability Registry merged through PR #225 to `3a53d44a77254810c701a04535b1ef2065302ab6`; post-merge docs `31257452439` and CI `31257452441` SUCCESS. |
| CORE-012 | PASS | Effective capability projection merged through PR #226 to `608bc854863c9e9fa756c20503c7c7d27d83d61a`; post-merge docs `31258381298` and CI `31258381284` SUCCESS. |
| CORE-013 | PASS | Fragmented UIContract storage merged through PR #227 to `9b1a8aeb3a9ab536d8b26eeaf45717e95fd34d86`; post-merge docs `31258954098` and CI `31258954095` SUCCESS. |
| CORE-014 | PASS | Per-fragment attestation merged through PR #228 to `66d03890492f072364c270b9a9c6b42958da086e`; post-merge docs `31259491871` and CI `31259491856` SUCCESS. |
| CORE-015 | PASS | Contract-set digest merged through PR #229 to `f41915de3dbdcb052993f1e31f2aca1637840add`; post-merge docs `31260020398` and CI `31260020388` SUCCESS. |
| CORE-016 | PASS | Closed locator strategy merged through PR #230 to `7c321271ce5eae042754f8b18480758b6cf0ead1`; post-merge docs `31261175335` and CI `31261175402` SUCCESS. |
| CORE-017 | PASS | Closed UI drift lifecycle merged through PR #231 to `b9322f676eddb06a22fe98ead9292f05f6fdc5ef`; post-merge docs `31264131559` and CI `31264131570` SUCCESS. |
| CORE-018 | PASS | Sanitized capability evidence persistence merged through PR #232 to `99f32929ab13c5068ac00410e8418abc9b8a7ef2`; post-merge docs `31264839172` and CI `31264839203` SUCCESS. |
| CORE-019 | PASS | Deterministic attestation workflow merged through PR #233 to `f7b89a4eb740fa561189bc1e62c4869d5242a644`; post-merge docs `31265582918` and CI `31265582939` SUCCESS. |
| CORE-020 | PASS | Versioned evidence lifetime/revalidation merged through PR #234 to `b60f9b80c22cba841265962d0308518b57667fd6`; post-merge docs `31266326587` and CI `31266326601` SUCCESS. |

Phase 2 gate: **PASS / GREEN** — CORE-011..020 are merged and all applicable post-merge gates completed successfully.

## Phase 3 — Browser, session and network hardening

| Key | Status | Evidence / decision |
|---|---|---|
| CORE-021 | PASS | FastAPI browser lifespan ownership merged through PR #235 to `f57514abf21188dd76a2065521506d9d2e18f5c7`; post-merge docs `31266922919` and CI `31266922911` SUCCESS. |
| CORE-022 | PASS | True liveness/readiness merged through PR #236 to `b3aef8e08f13621070e777bdca81921a95320aed`; post-merge docs `31267827191` and CI `31267827213` SUCCESS. Readiness is a fail-closed seven-signal AND gate over browser/profile/auth/UI contract/broker/protocol/lock. |
| CORE-023 | IMPLEMENTED_AWAITING_GATES | Canonical `SessionCapabilityBroker` binds registered semantic capability grants to the process-owned authenticated professional browser session. Grants contain bounded scope metadata only; no cookies, tokens, headers or storage state can be exported. Planner read endpoints now use semantic capability grants. |

## CORE-017..020 evidence/lifecycle boundary

UI lifecycle, evidence persistence, attestation and freshness remain separate reviewed concerns. Evidence is bound to the exact UIContractSet digest, contains no tenant/session content, and expiration/degradation is capability scoped. Current Planner fragments remain `UNVERIFIED_LIVE` until real controlled evidence is collected; no CI workflow authenticates to the real tenant.

## CORE-021 boundary decision

FastAPI lifespan is the explicit owner of the canonical browser object. Live lifecycle ownership covers both Playwright and the persistent Chromium context with deterministic cleanup. Browser process ownership is infrastructure state, not semantic authorization; CORE-025 remains mandatory before controlled live Microsoft 365 egress.

## CORE-022 boundary decision

`CORE-022` separates a responsive ASGI process from readiness for live Microsoft 365 work. `/livez` only asserts process liveness. `/readyz` is a seven-signal AND gate over browser ownership, profile usability, `AUTHENTICATED`, UIContract attestation, broker viability, protocol compatibility and lock viability. Providers belonging to later work remain fail closed until proven.

## CORE-023 boundary decision

`CORE-023` is a semantic authorization broker, not a credential broker. It receives the process-owned browser, the closed Capability Registry and an authentication-state provider. Viability requires both an owned browser and `AUTHENTICATED`; authorization additionally requires one unique registered application/capability and the existing UIContract live guard.

Successful grants contain application/surface/account/container/capability metadata plus explicit `session_bound=true` and `secret_material_exported=false`. There is no broker method that returns cookies, tokens, authorization headers, browser storage state or arbitrary page primitives. Account-context correctness remains CORE-024 and controlled egress remains CORE-025.

## Current compatibility invariants

- all 17 public `planner_*` tools remain `PRESERVE` under default profile;
- all 11 Planner capability keys are preserved;
- all 10 existing UI selectors are preserved exactly once and in historical order;
- mock mode cannot be interpreted as live support;
- Outlook remains `RESERVED`, with zero public tools/capabilities/selectors;
- no raw browser primitive/session-secret export is introduced;
- `CORE-025` remains mandatory before any automated live M365 worker egress/revalidation claim.

## Next gate

```text
CORE-023 PR CI/security/images/SBOM GREEN
        -> merge
        -> post-merge main GREEN
        -> CORE-024
```
