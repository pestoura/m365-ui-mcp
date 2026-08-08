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

Phase 1 gate: **PASS / GREEN** — all pre-transition Planner contract/tests remain GREEN.

## Phase 2 — Capability and UI contract redesign

| Key | Status | Evidence / decision |
|---|---|---|
| CORE-011 | PASS | Scoped Capability Registry merged through PR #225 to `3a53d44a77254810c701a04535b1ef2065302ab6`; PR docs `31257236487` and CI `31257236512` SUCCESS; post-merge docs `31257452439` and CI `31257452441` SUCCESS. Eleven Planner capability keys retain order and semantics with explicit app/surface/account/container scope. |
| CORE-012 | IMPLEMENTED_AWAITING_GATES | Effective projection combines registry, auth, account context, UI attestation, runtime health, current policy, licence and live-vs-mock boundary. Registry or mock evidence alone cannot promote support. |
| CORE-013 | NOT_STARTED | Fragmented UIContract storage. |
| CORE-014 | NOT_STARTED | Per-fragment attestation. |
| CORE-015 | NOT_STARTED | Contract-set digest. |
| CORE-016 | NOT_STARTED | Locator strategy abstraction. |
| CORE-017 | NOT_STARTED | UI drift lifecycle. |
| CORE-018 | NOT_STARTED | Capability evidence persistence. |
| CORE-019 | NOT_STARTED | Attestation tooling/runbook. |
| CORE-020 | NOT_STARTED | Capability expiration/revalidation. |

## CORE-012 boundary decision

Effective support is evidence-derived. Policy/runtime failures block; missing auth/account/UI/licence/live evidence remains `UNVERIFIED_LIVE`; only the complete live evidence set may become `READ_SUPPORTED`. Current global UIContract status is consumed without pretending fragmentation already exists.

The Planner public compatibility view remains 11 capability rows in the same order. `effective_projection` is additive scoped evidence metadata only.

## Current compatibility invariants

- all 17 public `planner_*` tools remain `PRESERVE` under default profile;
- all 11 Planner capability keys are preserved;
- mock mode cannot be interpreted as live support;
- Outlook remains `RESERVED`, with zero public tools/capabilities;
- no raw browser primitive/session-secret export is introduced;
- `CORE-025` remains mandatory before any live M365 worker egress claim.

## Next gate

```text
CORE-012 PR CI/security/images/SBOM GREEN
        -> merge
        -> post-merge main GREEN
        -> CORE-013
```
