# Planner MCP Traceability

This document maps the canonical specification to architectural decisions, backlog ownership,
testing and evidence. It is an audit index; it **does not redefine requirement IDs**. Normative
requirement IDs remain defined in their source documents.

Companions: [`backlog.md`](backlog.md), [`roadmap.md`](roadmap.md),
[`testing.md`](testing.md), [`acceptance.md`](acceptance.md),
[`release-process.md`](release-process.md) and [`definition-of-done.md`](definition-of-done.md).

## 1. Traceability rules

Every material product requirement must be traceable through as many of these layers as apply:

`requirement ID → canonical document → ADR → P-key → implementation → test → evidence → release`

A PR that adds or changes a product requirement, architectural decision, security control,
capability claim or test obligation updates this file in the same change.

Evidence rules:

- mock evidence proves implementation behaviour, not live Planner capability;
- live capability promotion requires browser/UI evidence;
- no capability may be marked supported solely from Microsoft documentation or Graph availability;
- no gate that failed to run may be recorded as PASS;
- sensitive tenant content, credentials, cookies, tokens and raw session material are not evidence
  artifacts suitable for the repository.

## 2. Requirement namespaces and canonical sources

| Namespace | Canonical source | Primary concern |
| --- | --- | --- |
| `ARCH-*` | [`architecture.md`](architecture.md) | system boundaries, execution chain, control-plane/worker split |
| `THR-*` | [`threat-model.md`](threat-model.md) | threats, abuse cases and mitigations |
| `SEC-*` | [`security.md`](security.md) | security controls and fail-closed rules |
| `GOV-*` | [`governance.md`](governance.md) | policy, approval and governance decisions |
| `PRIV-*` | [`privacy-boundary.md`](privacy-boundary.md) | personal-device and data boundary |
| `AUTH-*` | [`authentication-and-mfa.md`](authentication-and-mfa.md) | browser authentication, state machine and MFA |
| `UI-*` | [`ui-contract.md`](ui-contract.md) | selector contract, evidence, attestation and drift |
| `WORKER-*` | [`browser-worker.md`](browser-worker.md) | private browser-worker runtime and operation boundary |
| `CAP-*` | [`planner-premium-capabilities.md`](planner-premium-capabilities.md) | evidence-driven Planner Premium capability state |
| `TOOL-*` | [`tool-catalog.md`](tool-catalog.md) | semantic MCP tool contract and metadata |

A1.3 documents add detailed state, reconciliation, testing, deployment, observability, reporting and
release obligations. They reference the canonical namespaces above and may define additional stable
IDs where the document explicitly establishes them. IDs are never invented in this traceability file
to make a coverage table appear complete.

## 3. Architectural decisions

| ADR | Decision | Main specification | Primary backlog ownership |
| --- | --- | --- | --- |
| ADR-001 | Browser automation is the primary Planner implementation path | architecture, vision | P-011..P-017, P-025..P-030 |
| ADR-002 | Control plane and browser worker are separate trust/runtime boundaries | architecture, browser-worker | P-007, P-011, P-064 |
| ADR-003 | Reconciliation-first desired-state architecture | reconciliation, state-model | P-049..P-053 |
| ADR-004 | MFA is human-in-loop and approval occurs only in Microsoft Authenticator | authentication-and-mfa | P-018..P-023 |
| ADR-005 | `hermes-mcp-bridge` is a pattern baseline, not a fork or execution dependency | hermes-integration | cross-cutting foundation/governance |
| ADR-006 | UIContract is centralized, versioned, attested and fail-closed on drift | ui-contract, browser-worker | P-014..P-017 |
| ADR-007 | Dedicated professional browser profile preserves the personal-device privacy boundary | privacy-boundary, browser-worker | P-013, P-021, P-023, P-064 |
| ADR-008 | Microsoft Graph API is a non-dependency and never a functional capability gate | architecture, capabilities | P-024 and all capability discovery |

Only ADR-001..ADR-008 are canonical at A1 closure. A later ADR uses the next sequential identifier
and must update this table.

## 4. EPIC ↔ specification ↔ evidence map

| EPIC | P-keys | Canonical specification | Minimum proving layers |
| --- | --- | --- | --- |
| EPIC-01 Foundation | P-001..P-010 | vision, architecture, threat-model, security, governance, contracts, state foundations | docs validation, compile, lint/type, unit/schema/contract, secret scan |
| EPIC-02 Browser Worker / UI | P-011..P-017 | browser-worker, ui-contract, ADR-002, ADR-006, ADR-007 | unit/contract, mock UI, isolated browser, selector-attestation evidence |
| EPIC-03 Authentication / MFA | P-018..P-024 | authentication-and-mfa, privacy-boundary, ADR-004, ADR-007, ADR-008 | auth-state tests, MFA/CA/enrolment fixtures, live operator evidence when applicable |
| EPIC-04 Read Model | P-025..P-030 | tool-catalog, capabilities, state-model | schema/contract, mock UI, isolated acceptance, live read-only attestation for live claims |
| EPIC-05 Mutations | P-031..P-036 | idempotency, governance, reconciliation, security | policy/approval/idempotency/lock/read-back tests; live mutation acceptance only in isolated test plan and later release |
| EPIC-06 Scheduling / PM | P-037..P-045 | capabilities, reconciliation, state-model | semantic/unit tests, mock UI, capability-specific live evidence before promotion |
| EPIC-07 Reconciliation / Blueprints | P-046..P-053 | reconciliation, idempotency, state-model | diff/plan/checkpoint/saga tests, dry-run evidence, isolated acceptance |
| EPIC-08 Reporting / Portfolio | P-054..P-060 | reporting, capabilities, state-model | report-schema tests, freshness/provisional-state tests, telemetry hygiene |
| EPIC-09 Security / Governance / Observability | P-061..P-067 | security, governance, observability, deployment | policy/approval tests, secret scan, Trivy, SBOM, container posture, audit reconstruction |
| EPIC-10 Acceptance / Release | P-068..P-074 | testing, acceptance, release-process, definition-of-done, this file | complete CI, IA-01..IA-16, traceability/docs gates, post-merge evidence, live read-only evidence where claimed |

## 5. 0.1.0 public contract traceability

Release `0.1.0` is read-only. The public contract contains exactly 17 tools and every tool is
classified `READ` in this release.

| Capability group | Public tools | Primary P-keys | Evidence before release |
| --- | --- | --- | --- |
| Service/contract | `planner_health`, `planner_readiness`, `planner_agent_card` | P-004, P-005, P-007 | schema/contract + isolated smoke |
| Capability/UI status | `planner_capabilities`, `planner_ui_contract_status`, `planner_license_capabilities` | P-014..P-017, P-024 | contract + mock evidence; live state remains unverified until live attestation |
| Authentication state | `planner_auth_status`, `planner_auth_start`, `planner_auth_resume`, `planner_auth_session_info` | P-018..P-023 | auth-state/MFA/CA/enrolment tests; no credentials stored |
| Plan reads | `planner_plan_list`, `planner_plan_get` | P-025, P-026 | schema + mock/isolated read evidence; live evidence for live claim |
| Task reads | `planner_task_list`, `planner_task_get` | P-027 | schema + mock/isolated read evidence; live evidence for live claim |
| Composite read | `planner_project_snapshot` | P-028..P-030 | consistent composite snapshot + stable hash evidence |
| Context/smoke | `planner_account_context`, `planner_smoke_test` | P-024, P-069 | ambiguity/blocker tests + isolated smoke |

P-031 and P-050 may supply internal safety/reconciliation infrastructure on the program critical
path, but no public mutation or tenant `apply` operation is registered in 0.1.0. Their presence in
code is not evidence of exposed write capability.

## 6. Critical-path traceability

The canonical path is fixed by the backlog:

`P-001 → P-011 → P-014 → P-018 → P-025 → P-026 → P-027 → P-030 → P-031 → P-050 → P-069 → P-071 → P-073 → P-074`

| Order | Key | Canonical meaning | Closing evidence |
| ---: | --- | --- | --- |
| 1 | P-001 | Repository, specification and CI foundation | canonical docs + validation evidence |
| 2 | P-011 | FastAPI worker skeleton with typed operation envelope | schema/negative tests + private topology evidence |
| 3 | P-014 | Centralized UIContract loader with attestation gating | contract tests + unattested refusal |
| 4 | P-018 | Formal auth state machine | exhaustive transition tests |
| 5 | P-025 | Plan/project list read | schema-valid deterministic read evidence |
| 6 | P-026 | Plan/project detail read | schema-valid detail read evidence |
| 7 | P-027 | Task list and task detail reads | normalized task-read evidence |
| 8 | P-030 | Project snapshot with stable hash | repeat-read hash equality |
| 9 | P-031 | Mutation framework safety boundary | policy/approval/idempotency/lock/read-back framework tests; not a 0.1 write claim |
| 10 | P-050 | Desired-state reconciliation engine | deterministic diff/checkpoint/mock execution evidence; live apply disabled in 0.1 |
| 11 | P-069 | Isolated acceptance IA-01..IA-16 | acceptance evidence bundle |
| 12 | P-071 | Traceability matrix closure | zero orphan requirement/test mapping gate |
| 13 | P-073 | Release process and gates | release workflow/gate evidence |
| 14 | P-074 | `0.1.0` release | exact-SHA release evidence, SBOMs, known blockers, truthful capability matrix |

## 7. Security/privacy control traceability

| Control objective | Sources / ADRs | Backlog | Required proof |
| --- | --- | --- | --- |
| No generic browser primitives exposed | architecture, browser-worker, tool-catalog; ADR-001/002 | P-007, P-011 | registry/schema negative tests |
| No Intune/MDM/Entra-device enrolment or compliance spoofing | privacy-boundary, security; ADR-007 | P-013, P-021, P-023, P-064 | refusal fixtures + static/runtime posture checks |
| Password/tokens/cookies are not system data | authentication-and-mfa, privacy-boundary | P-018..P-024, P-063 | schema/storage/log negative tests |
| MFA approval only in Microsoft Authenticator | authentication-and-mfa; ADR-004 | P-020 | MFA fixture + event-schema test |
| UI drift fails closed | ui-contract; ADR-006 | P-014..P-017 | drift fixture + zero mutation after mismatch |
| Policy fails closed | governance, security | P-031, P-061 | invalid/missing policy denial tests |
| Approval is persistent, single-use and bound to the exact operation | governance | P-062 | replay/change/expiry negative tests |
| Mutation retry never occurs blindly | idempotency, reconciliation | P-031, P-066 | timeout/read-back/unknown-outcome tests |
| Container boundary is hardened | deployment, privacy-boundary | P-064 | non-root/read-only/cap-drop/no-new-privileges/no-host-mount checks |
| Supply chain is evidenced | deployment, release-process | P-065, P-068 | Trivy, real digest pinning, CycloneDX SBOM validation |
| Telemetry is redacted and low-cardinality | observability, security | P-008, P-009, P-063 | adversarial redaction + metric-label tests |
| Operator-only GUI handoff is host-side, loopback-only, fail-closed | browser-worker, operator-gui-handoff; WORKER-120…127 | P-007, P-064 | preflight/teardown/rollback tests + loopback/CDP/chown assertion tests |

## 8. Capability claim traceability

A capability state advances only when the evidence required by
[`planner-premium-capabilities.md`](planner-premium-capabilities.md) exists.

| State | Minimum meaning |
| --- | --- |
| `UNVERIFIED_LIVE` | specified only; no tenant evidence |
| `DISCOVERED` | observed in the real tenant/UI |
| `READ_ATTESTED` | read path and UIContract evidence validated |
| `MUTATION_ATTESTED` | governed mutation and read-back validated in an authorized isolated plan |
| `SUPPORTED` | all product, security, UIContract, evidence and release gates for that capability pass |
| `DEGRADED` | capability remains bounded but an expected dependency/condition is degraded |
| `UI_DRIFT` | contract mismatch; fail closed until re-attested |
| `BLOCKED_CONDITIONAL_ACCESS` | tenant policy requires an unacceptable/unsupported device condition |

Microsoft Graph availability is not an evidence column and never promotes or blocks these states.

## 9. Release evidence mapping

| Release concern | Backlog owner | Evidence |
| --- | --- | --- |
| Complete CI | P-068 | exact-SHA workflow/check results |
| Isolated acceptance | P-069 | IA-01..IA-16 result bundle |
| Live read-only protocol | P-070 | sanitized operator record or explicit blocker |
| Traceability closure | P-071 | traceability validator output |
| Documentation completeness | P-072 | docs validator output with `errors=0`, `warnings=0` |
| Release gates | P-073 | release gate record + post-merge verification |
| 0.1.0 release | P-074 | tag/release, SBOMs, image digests, capability matrix, known blockers |

If GitHub Actions or another required external gate is unavailable, the evidence state is
`BLOCKED/UNAVAILABLE`, not PASS, and merge/release waits for restoration.

## 10. Change discipline

Any new requirement discussed during development must end up in the repository as a requirement ID
and/or canonical documentation, backlog ownership, implementation, tests and release evidence as
appropriate. Architectural decisions receive an ADR; capability additions update the capability
matrix and backlog; security controls update the threat/security model plus tests. Important product
knowledge must not exist only in chat history.
