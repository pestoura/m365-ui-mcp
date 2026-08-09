# PLN-MIG-008 — Planner mock parity suite

Status: **IMPLEMENTED_LOCAL_GATES_GREEN**

## Objective

Prove that the generalized M365 platform extraction did not change any preserved Planner semantic output for an unchanged contract, by comparing normalized mock outputs of the complete 17-tool `planner_*` public surface against a frozen parity baseline.

## Mechanism

- `m365_mcp.apps.planner.mock_parity` provides deterministic normalization (`normalize`, `normalize_envelope`, `parity_snapshot`) and a stable `parity_digest`.
- Normalization masks only legitimately non-deterministic values (`expires_at`, `generated_at`, `timestamp`, `ts`, `duration_s`, `duration_ms`, `started_at`, `completed_at`, `operation_id`). No semantic payload and no governance flag is removed.
- `tests/data/planner_mock_parity_baseline.json` freezes the normalized output of all 17 tools plus the aggregate digest.
- `tests/test_planner_mock_parity.py` executes the full public surface against the in-process mock worker and asserts baseline equality, run-to-run determinism, governance-flag preservation, masking scope and digest sensitivity.

## Parity result

- covered tools: 17, exactly `PLANNER_PUBLIC_TOOL_NAMES` in canonical order;
- baseline digest: `sha256:fdd974d0f8d07a1d4c999d5ba2216c6fdd9e87ca75c535fa73560a900195501a`;
- observed digest on this branch: identical;
- `read_only=true` and `graph_api_used=false` preserved on all 17 envelopes;
- `planner_smoke_test.mutations_performed == 0`.

## Truthfulness boundary

Mock parity is mock-only. The baseline records `"live_support_claimed": false`. This gate does **not** attest live UI behavior, does not promote any capability to `READ_SUPPORTED`/`MUTATION_SUPPORTED`, and does not change policy, capability or mutation semantics. Live read parity remains PLN-MIG-010.

## Security posture

No credential material, no tenant data and no absolute filesystem path is stored: the baseline contains only synthetic mock data and already-redacted configuration values (`[REDACTED]`). `scripts/check_no_secrets.py` passes.

## Current integration gate

This branch is cut from current remote `main` at `2ff95b0` (merge of PR #295). Local gates (compileall, ruff, mypy, check_docs, check_contracts, full pytest, isolated_acceptance, check_no_secrets) are GREEN on this base. Merge only after pull-request CI/security/documentation gates are also GREEN.
