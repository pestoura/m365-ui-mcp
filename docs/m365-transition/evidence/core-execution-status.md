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
| CORE-012 | PASS | Effective capability projection merged through PR #226 to `608bc854863c9e9fa756c20503c7c7d27d83d61a`; PR docs `31258209123` and CI `31258209104` SUCCESS; post-merge docs `31258381298` and CI `31258381284` SUCCESS. Mock or mode flags cannot promote live support without explicit live-UI evidence provenance. |
| CORE-013 | PASS | Fragmented UIContract storage merged through PR #227 to `9b1a8aeb3a9ab536d8b26eeaf45717e95fd34d86`; PR docs `31258776662` and CI `31258776663` SUCCESS; post-merge docs `31258954098` and CI `31258954095` SUCCESS. Ten legacy selectors remain exactly preserved and globally compatible. |
| CORE-014 | PASS | Per-fragment attestation merged through PR #228 to `66d03890492f072364c270b9a9c6b42958da086e`; PR docs `31259317512` and CI `31259317510` SUCCESS; post-merge docs `31259491871` and CI `31259491856` SUCCESS. Drift affects only capabilities with explicit fragment dependencies. |
| CORE-015 | PASS | Contract-set digest merged through PR #229 to `f41915de3dbdcb052993f1e31f2aca1637840add`; PR docs `31259832059` and CI `31259832057` SUCCESS; post-merge docs `31260020398` and CI `31260020388` SUCCESS. Deterministic SHA-256 identifies the exact semantic contract set without runtime/session identity. |
| CORE-016 | PASS | Closed locator strategy merged through PR #230 to `7c321271ce5eae042754f8b18480758b6cf0ead1`; post-merge docs `31261175335` and CI `31261175402` SUCCESS. Accessible semantics outrank evidence-bound test-id/CSS fallbacks; unsafe generic primitives remain rejected. |
| CORE-017 | IMPLEMENTED_AWAITING_GATES | Closed `HEALTHY`/`STALE`/`DRIFTED`/`RE_ATTESTATION_REQUIRED` lifecycle, fail-closed transitions and dependent-capability degradation implemented without persisting or inventing live evidence. |
| CORE-018 | NOT_STARTED | Capability evidence persistence. |
| CORE-019 | NOT_STARTED | Attestation tooling/runbook. |
| CORE-020 | NOT_STARTED | Capability expiration/revalidation. |

## CORE-017 boundary decision

Lifecycle semantics are deliberately separate from evidence persistence and aging policy. `CORE-017` provides a closed state/event model and capability-scoped degradation. `CORE-018` owns sanitized evidence persistence; `CORE-020` owns expiration/revalidation policy.

A contract-recorded drift cannot be hidden by runtime lifecycle input, and a lifecycle overlay cannot promote an unattested fragment to healthy. Recovery from drift requires an explicit `RE_ATTESTATION_REQUIRED` state before successful re-attestation can return evidence to `HEALTHY`.

## Current compatibility invariants

- all 17 public `planner_*` tools remain `PRESERVE` under default profile;
- all 11 Planner capability keys are preserved;
- all 10 existing UI selectors are preserved exactly once and in historical order;
- mock mode cannot be interpreted as live support;
- Outlook remains `RESERVED`, with zero public tools/capabilities/selectors;
- no raw browser primitive/session-secret export is introduced;
- `CORE-025` remains mandatory before any live M365 worker egress claim.

## Next gate

```text
CORE-017 PR CI/security/images/SBOM GREEN
        -> merge
        -> post-merge main GREEN
        -> CORE-018
```
