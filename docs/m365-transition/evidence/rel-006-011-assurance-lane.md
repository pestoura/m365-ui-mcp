# REL-006..REL-011 — Assurance lane (Lane E)

Status: **IMPLEMENTED_ON_CURRENT_MAIN_GATES_GREEN**

Scope: Phase 16 assurance items that are justified now, on mock/isolated evidence only.
No live tenant evidence exists, therefore **no REL-012+ live acceptance is claimed**.

## Classification

| Item | Prior state | Action taken |
| --- | --- | --- |
| REL-006 Tool Registry schema/consistency | Partially satisfied (`tests/test_tool_registry.py`, `test_planner_application_tool_registry.py`) — Planner-specific | Strengthened: application-neutral invariants over every definition (namespace prefixes, well-formed object schemas, `required ⊆ properties`, deterministic ordering, snapshot completeness without schema leakage, manifest agreement, no unattested `IMPLEMENTED_LIVE`, read-back required for non-READ, unknown-application rejection) |
| REL-007 Capability/UIContract consistency | Partially satisfied (`test_scoped_capability_registry.py` covered tool→capability only) | Strengthened: tool→capability, tool→selector, single-fragment selector ownership, fragment→capability, capability→fragment resolution, and repo-wide no-live-attestation invariant |
| REL-008 Policy metadata completeness | Not satisfied as a gate (behaviour tested, completeness not gated) | New executable gate `scripts/check_policy_metadata.py` (+ CI step) and `tests/test_rel_008_policy_metadata_gate.py` |
| REL-009 No generic browser operation | Partially satisfied (three per-module tests) | Strengthened: repository-wide regression across public tool names, worker operation enum, envelope schemas, control-plane module sources and tool input schemas |
| REL-010 Secret/session exfiltration | Partially satisfied (`test_redaction_logging.py`, 3 unit tests) | Strengthened: end-to-end recursive scan of all 17 mock tool results, registry/capability/UIContract snapshots, all contract documents, and structured logs |
| REL-011 Mock/isolated acceptance | Satisfied but unmapped | Strengthened: every acceptance check now carries its canonical `IA-nn` scenario; three checks added (mock-mode enforcement, snapshot determinism, fail-closed policy on unregistered tool); suite integrity asserted by tests |

## Files

- `tests/test_rel_006_tool_registry_consistency.py` (new, 9 tests)
- `tests/test_rel_007_capability_ui_contract_consistency.py` (new, 7 tests)
- `scripts/check_policy_metadata.py` (new gate)
- `tests/test_rel_008_policy_metadata_gate.py` (new, 4 tests)
- `tests/test_rel_009_no_generic_browser_operations.py` (new, 6 tests)
- `tests/test_rel_010_secret_exfiltration_regression.py` (new, 6 tests)
- `tests/test_rel_011_isolated_acceptance_suite.py` (new, 4 tests)
- `scripts/isolated_acceptance.py` (modified: IA scenario mapping + 3 checks + report metadata)
- `.github/workflows/ci.yml` (modified: REL-008 gate step)

No feature implementation module was modified. No product behaviour changed.

## Validation

| Gate | Result |
| --- | --- |
| `compileall src tests scripts` | PASS |
| `ruff check .` | PASS |
| `mypy` | PASS (121 source files) |
| `scripts/check_docs.py` | PASS (0 errors, 0 warnings) |
| `scripts/check_contracts.py` | PASS |
| `scripts/check_policy_metadata.py` | PASS (17 tools, 0 violations) |
| `scripts/check_no_secrets.py` | PASS |
| `scripts/check_base_image_pinning.py` | PASS |
| `scripts/isolated_acceptance.py` | PASS (25 checks, 10 IA families, 0 unmapped) |
| `pytest` | 479 passed (baseline on `main` @ 96cee6d: 443) |

Negative controls were exercised locally for the REL-010 detector: injected
`{"token": ...}`, `Bearer ...` and `{"cookie": ...}` payloads all fail the
assertion, so the suite is not vacuously green.

## Limitations

- All evidence is mock/isolated. No Microsoft 365 tenant was contacted.
- REL-012..REL-024 remain open and are explicitly **not** claimed.
- REL-001..REL-005 (threat model, trust boundary, privacy review, container
  hardening parity, egress acceptance) are out of scope for this lane.
- The Outlook surface remains `RESERVED`; these controls assert that it stays
  inert rather than validating any Outlook behaviour.
