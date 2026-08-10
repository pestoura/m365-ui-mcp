# REL-006..REL-012 — Hardening lane B (assurance acceptance)

Status: **IMPLEMENTED_MOCK_ONLY / REPOSITORY-SIDE, GATES GREEN**

Scope: the Phase 16 assurance items that are provable with repository, mock and
isolated evidence only. **No Microsoft 365 tenant was contacted.** No browser
session was started, no capability was promoted, and no live acceptance is
claimed by any item in this lane.

## Relationship to prior work

REL-006..REL-011 were implemented and merged to `main` by PR #322
(`chore(assurance): REL-006..REL-011 assurance lane (clean)`, merge commit
`dd7b85e192af12ecc90f0984755eeb250c6e9589`), with the substantive record in
[`rel-006-011-assurance-lane.md`](rel-006-011-assurance-lane.md). Those items
were never carried through the controller, so the execution index still showed
them as unmaterialized. This lane materializes them against the delivered
mechanisms and adds the one item that was still genuinely open, REL-012.

Nothing in REL-006..REL-011 is re-implemented here. Re-implementing merged,
gate-green work would duplicate content and destroy the mapping between the
index entry and the PR that actually delivered it.

## Item classification

| Item | Delivered by | Mechanism on current `main` | Verdict |
| --- | --- | --- | --- |
| REL-006 Tool Registry schema/consistency tests | PR #322 | `tests/test_rel_006_tool_registry_consistency.py` — 9 application-neutral invariants over every registry definition (namespace prefixes, well-formed object schemas, `required ⊆ properties`, deterministic ordering, snapshot completeness without schema leakage, manifest agreement, no unattested `IMPLEMENTED_LIVE`, read-back required for non-READ, unknown-application rejection) | ACCEPTED |
| REL-007 Capability/UIContract consistency gates | PR #322 | `tests/test_rel_007_capability_ui_contract_consistency.py` — 7 tests over tool→capability, tool→selector, single-fragment selector ownership, fragment→capability, capability→fragment resolution and the repo-wide no-live-attestation invariant | ACCEPTED |
| REL-008 Policy metadata completeness gate | PR #322 | `scripts/check_policy_metadata.py` executable gate, wired as a blocking CI step, plus `tests/test_rel_008_policy_metadata_gate.py` (4 tests). Current run: 17 tools checked, 0 violations | ACCEPTED |
| REL-009 No generic browser-operation regression test | PR #322 | `tests/test_rel_009_no_generic_browser_operations.py` — 6 repository-wide regressions across public tool names, the worker operation enum, envelope schemas, control-plane module sources and tool input schemas | ACCEPTED |
| REL-010 Secret/session exfiltration regression suite | PR #322 | `tests/test_rel_010_secret_exfiltration_regression.py` — 6 tests recursively scanning all 17 mock tool results, registry/capability/UIContract snapshots, all contract documents and structured logs | ACCEPTED |
| REL-011 Mock/isolated acceptance suite | PR #322 | `scripts/isolated_acceptance.py` with every check mapped to a canonical `IA-nn` scenario from `docs/acceptance.md`, asserted by `tests/test_rel_011_isolated_acceptance_suite.py` (4 tests). Current run: 0 unmapped checks | ACCEPTED |
| REL-012 Planner parity acceptance | **this lane** | `tests/test_rel_012_planner_parity_acceptance.py` (new, 8 tests) | ACCEPTED |

## REL-012 — what was actually missing

PLN-MIG-008 froze the normalized mock output of the 17-tool preserved Planner
public ABI, and PLN-MIG-009 froze its governance projection. Each suite proves
its own mechanism. Neither states the acceptance claim that the two are
supposed to jointly support, and — importantly — neither prevents parity from
being declared from a stale half: output parity could be green in one run while
governance parity was last observed in another.

`tests/test_rel_012_planner_parity_acceptance.py` asserts the acceptance claim
itself:

1. both baselines describe the same, complete, canonically ordered 17-tool ABI
   (`PLANNER_PUBLIC_TOOL_NAMES`, no duplicates);
2. neither baseline claims live support, and no governance record carries
   `IMPLEMENTED_LIVE`;
3. the observed output digest and the observed governance digest both match
   their frozen baselines **in the same test run**, together with
   `governance_regressions() == ()`;
4. every preserved tool is `MutationClass.READ` with `read_only=true` and
   `graph_api_used=false`, and no capability constraint was dropped;
5. the acceptance is falsifiable: perturbing the output baseline changes the
   digest, and weakening `planner_task_get`'s security tier is reported as a
   regression;
6. neither baseline contains tenant, credential or filesystem material.

## Files

- `tests/test_rel_012_planner_parity_acceptance.py` (new, 8 tests)
- `docs/m365-transition/evidence/rel-006-012-assurance-acceptance-lane.md` (this record)

No feature module, no tool registration, no capability definition, no contract
and no policy was modified. The public projection remains exactly the 17
Planner `READ` tools.

## Negative controls

Parity acceptance is not vacuously green:
`test_parity_acceptance_is_falsifiable_on_output_drift` flips
`planner_plan_list.read_only` in a copy of the baseline and asserts the digest
moves; `test_parity_acceptance_is_falsifiable_on_governance_drift` lowers
`planner_task_get` to tier 0 and asserts both a digest change and a reported
regression. If the parity mechanisms stopped detecting drift, these two tests
go red.

## Validation

| Gate | Result |
| --- | --- |
| `compileall src tests scripts` | PASS |
| `ruff check .` | PASS |
| `mypy` | PASS |
| `scripts/check_docs.py` | PASS (0 errors, 0 warnings) |
| `scripts/check_contracts.py` | PASS (17 tools) |
| `scripts/check_policy_metadata.py` | PASS (17 tools, 0 violations) |
| `scripts/check_no_secrets.py` | PASS |
| `scripts/check_base_image_pinning.py` | PASS |
| `scripts/check_execution_index.py` | `EXECUTION_INDEX_OK` |
| `scripts/isolated_acceptance.py` | PASS (0 unmapped checks) |
| `pytest` | full suite PASS |

## Limitations

- All evidence is repository/mock/isolated. **No tenant, no browser session, no
  authenticated request.**
- REL-013..REL-016 (Outlook read-only, Outlook safe-write, governed outbound
  mail, calendar governed-write) are LIVE acceptance items. They are **not**
  attempted here and remain blocked on real authenticated tenant evidence
  including MFA / Conditional Access handling and UI attestation.
- Outlook stays `RESERVED`, `LIVE UNOBSERVED`, with zero public tools.
  XAPP-029 stays `DEFERRED`.
- Mock parity is mock parity: it proves the extraction did not change preserved
  semantics for an unchanged contract. It attests nothing about live Planner UI
  behaviour, which remains PLN-MIG-010 / A3 territory.
- `SEC-070`/`SEC-071` remain `PLANNED`; this lane did not change them.
