# PLN-MIG-009 — Planner policy parity suite

Status: **IMPLEMENTED_LOCAL_GATES_GREEN**

## Objective

Prove that no operation of the preserved 17-tool `planner_*` public surface became *less governed* after the generalized M365 platform extraction. Policy parity freezes the canonical governance projection of every preserved tool and fails closed on any weakening.

## Mechanism

- `m365_mcp.apps.planner.policy_parity` projects, per tool, the sanitized governance record derived from the canonical reviewed metadata and the shared `MetadataPolicyEngine`: application, surface, domain, mutation class, risk class, implementation state, compatibility requirement, approval requirement, capability keys, decision, reason, security tier and derived policy scope.
- `governance_regressions()` compares a live projection against a frozen baseline and reports a regression on a weaker decision, a lower security tier, a dropped approval requirement, a lost capability constraint or a missing tool.
- `tests/data/planner_policy_parity_baseline.json` freezes the governance record of all 17 tools in canonical ABI order plus the aggregate digest.
- `scripts/emit_planner_policy_parity_baseline.py` regenerates that baseline deterministically.
- `tests/test_planner_policy_parity.py` asserts baseline equality, determinism, regression detection, read/mutation classification, fail-closed behavior, capability-state enforcement, scope semantics, Graph non-usage and Planner→M365 policy delegation.

## Parity result

- covered tools: 17, exactly `PLANNER_PUBLIC_TOOL_NAMES` in canonical order;
- baseline digest: `sha256:105dd28c38b7b42fcf957b9b0622640827b0e4ea7a524ca94e0c364b4fe715bf`;
- observed digest on this branch: identical;
- decisions: all 17 `ALLOW` with reason `REGISTERED_READ_TOOL` under default `Settings()` (`allow_mutations=False`);
- mutation classification: all 17 `MutationClass.READ`, `compatibility_requirement=PRESERVE`, `approval_requirement="none"`;
- security tiers: T0 for `planner_health`, `planner_readiness`, `planner_capabilities`, `planner_agent_card`, `planner_ui_contract_status`, `planner_smoke_test`; T1 for the four auth tools, `planner_account_context` and `planner_license_capabilities`; T2 for the five Planner content reads;
- scope: every tool derives `CANONICAL_SCOPE_DERIVED` from Tool/Capability Registry metadata (`scope_derived=true`); explicit canonical scope is accepted as `SCOPE_VERIFIED`; a widened container scope is denied `SCOPE_CONTAINER_MISMATCH`;
- fail-closed: unregistered names (e.g. `planner_task_create`) are denied `TOOL_NOT_REGISTERED`; the compatibility `mutation=True` override denies all 17 with `MUTATIONS_DISABLED_IN_0_1_0` and can only be stricter;
- capability state: with all evidence present but `live_evidence=False`, every Planner scoped capability stays `UNVERIFIED_LIVE` / `supported=false` with `LIVE_EVIDENCE_ABSENT`; `policy_allowed=False` forces `BLOCKED` / `POLICY_DENIED`;
- no Graph: every preserved output schema requires `graph_api_used` with `{"const": false}` and `read_only` with `{"const": true}`;
- delegation: `planner_mcp.policy.evaluate`/`Decision` are the M365 engine objects and `READ_TOOLS` equals the 17-name ABI set.

## Truthfulness boundary

Policy parity is a governance projection over reviewed metadata in mock mode. It does **not** attest live UI behavior, does not promote any capability to `READ_SUPPORTED`/`MUTATION_SUPPORTED`, and adds no mutation support. Live read parity remains PLN-MIG-010; mutation parity remains PLN-MIG-011 and is only applicable if writes are promoted.

## Security posture

The projection contains policy classes only: no tokens, cookies, storage state, mailbox addresses, tenant identifiers or filesystem paths. A dedicated test asserts absence of that material in the serialized projection. `scripts/check_no_secrets.py` passes.

## Current integration gate

This branch is cut from remote `main` at `96cee6d` (OUT-010 message list merged, PLN-MIG-008 included). Local gates (compileall, ruff, mypy, check_docs, check_contracts, full pytest, isolated_acceptance, check_no_secrets) are GREEN on this base. Merge is **not** performed by this lane: main integration is owned exclusively by the controller lane during the urgent Outlook chain. This branch is prepared and pushed for review only.

## Downstream readiness

See [`pln-mig-010-012-readiness.md`](pln-mig-010-012-readiness.md) for the truthful PLN-MIG-010/011/012 assessment and the exact live-authentication blockers.
