# Backlog P-001..P-074

Canonical backlog for planner-mcp. Machine-readable source of truth: `docs/backlog.json`.

Graph API availability never determines scope or support level; the execution path is Planner Premium UI via Playwright/Chromium.

## Critical path

`P-001 -> P-011 -> P-014 -> P-018 -> P-025 -> P-026 -> P-027 -> P-030 -> P-031 -> P-050 -> P-069 -> P-071 -> P-073 -> P-074`

## Epics

| Epic | Title | Items |
| --- | --- | --- |
| EPIC-01 | Foundation, packaging and release contract | P-001..P-010 (10) |
| EPIC-02 | Security, policy and privacy boundary | P-011..P-020 (10) |
| EPIC-03 | Browser worker and Chromium profile isolation | P-021..P-030 (10) |
| EPIC-04 | Authentication, MFA and session lifecycle | P-031..P-040 (10) |
| EPIC-05 | UIContract attestation and drift management | P-041..P-050 (10) |
| EPIC-06 | Planner Premium read surface | P-051..P-060 (10) |
| EPIC-07 | State, idempotency, locks, sagas and reconciliation | P-061..P-068 (8) |
| EPIC-08 | Observability, reporting and evidence | P-069..P-071 (3) |
| EPIC-09 | Deployment, Cloudflare portal and Hermes integration | P-072..P-073 (2) |
| EPIC-10 | Mutation readiness and 0.2.0 roadmap | P-074..P-074 (1) |

## Items

| ID | Epic | Title | Depends on |
| --- | --- | --- | --- |
| P-001 | EPIC-01 | Repository bootstrap and branch protection baseline | - |
| P-002 | EPIC-01 | Python 3.12+ packaging with hatchling and src layout | P-001 |
| P-003 | EPIC-01 | Versioned JSON contracts packaged with the wheel | P-002 |
| P-004 | EPIC-01 | Product/schema/contract version metadata alignment | - |
| P-005 | EPIC-01 | Ruff and mypy strict configuration | - |
| P-006 | EPIC-01 | Pytest harness with mock-mode default | - |
| P-007 | EPIC-01 | Release contract validation test suite | P-003 |
| P-008 | EPIC-01 | CHANGELOG and semantic versioning policy | - |
| P-009 | EPIC-01 | Wheel and sdist build validation in CI | - |
| P-010 | EPIC-01 | Contributor and code ownership documentation | - |
| P-011 | EPIC-02 | Fail-closed policy engine ALLOW/DENY/REQUIRE_APPROVAL | P-001 |
| P-012 | EPIC-02 | Secret redaction library and log scrubbing | - |
| P-013 | EPIC-02 | No-secrets-in-state invariant tests | - |
| P-014 | EPIC-02 | Threat model documentation and review | P-011 |
| P-015 | EPIC-02 | Container hardening: non-root, cap-drop, no-new-privileges | - |
| P-016 | EPIC-02 | Read-only rootfs and tmpfs mounts | - |
| P-017 | EPIC-02 | Trivy CRITICAL/HIGH gate in CI | - |
| P-018 | EPIC-02 | Secret scanning gate in CI | P-014 |
| P-019 | EPIC-02 | CycloneDX SBOM generation and validation for both images | - |
| P-020 | EPIC-02 | Base image digest pinning gate | - |
| P-021 | EPIC-03 | Browser worker FastAPI skeleton | - |
| P-022 | EPIC-03 | Persistent Chromium profile abstraction | - |
| P-023 | EPIC-03 | Professional profile isolation from personal browser data | - |
| P-024 | EPIC-03 | No-enrolment invariant: Intune/Company Portal/MDM forbidden | - |
| P-025 | EPIC-03 | Conditional Access detection and BLOCKER_CONDITIONAL_ACCESS | P-018 |
| P-026 | EPIC-03 | Worker private network only, no public port | P-025 |
| P-027 | EPIC-03 | Playwright image build and pwuser runtime | P-026 |
| P-028 | EPIC-03 | Worker health endpoint and readiness semantics | - |
| P-029 | EPIC-03 | Mock mode data fixtures for CI | - |
| P-030 | EPIC-03 | Live mode fail-closed gate wired to UIContract attestation | P-019, P-025, P-027 |
| P-031 | EPIC-04 | Auth state machine with eight states | P-030 |
| P-032 | EPIC-04 | Auth start/resume worker endpoints | - |
| P-033 | EPIC-04 | MFA number matching detection (2-digit) | - |
| P-034 | EPIC-04 | Sanitized MFA metadata contract | - |
| P-035 | EPIC-04 | Authenticator-only approval invariant (never Telegram) | - |
| P-036 | EPIC-04 | Session expiry detection and recovery | - |
| P-037 | EPIC-04 | Account context sanitization | - |
| P-038 | EPIC-04 | License capability evidence extraction | - |
| P-039 | EPIC-04 | Auth telemetry and low-cardinality metrics | - |
| P-040 | EPIC-04 | Auth documentation and runbook | - |
| P-041 | EPIC-05 | Centralized versioned UIContract under browser/selectors | P-021 |
| P-042 | EPIC-05 | UNVERIFIED_LIVE selector marking and lint | P-041 |
| P-043 | EPIC-05 | UI_CONTRACT_UNATTESTED fail-closed enforcement | P-042 |
| P-044 | EPIC-05 | UI_DRIFT detection between worker and control plane | P-043 |
| P-045 | EPIC-05 | Selector attestation procedure and evidence format | - |
| P-046 | EPIC-05 | UIContract versioning and migration policy | - |
| P-047 | EPIC-05 | Mock UI harness for CI selector tests | - |
| P-048 | EPIC-05 | Drift alerting and metrics | - |
| P-049 | EPIC-05 | Attestation storage in state database | - |
| P-050 | EPIC-05 | Live read-only attestation campaign (separate from CI) | P-031 |
| P-051 | EPIC-06 | planner_plan_list read tool | P-030 |
| P-052 | EPIC-06 | planner_plan_get read tool | - |
| P-053 | EPIC-06 | planner_task_list read tool | - |
| P-054 | EPIC-06 | planner_task_get read tool | - |
| P-055 | EPIC-06 | planner_project_snapshot composite read | P-051, P-053 |
| P-056 | EPIC-06 | Bucket domain read model | - |
| P-057 | EPIC-06 | Dependency domain read model | - |
| P-058 | EPIC-06 | Scheduling domain read model | - |
| P-059 | EPIC-06 | Goals, sprints and resources read models | - |
| P-060 | EPIC-06 | Custom fields and portfolios read models | - |
| P-061 | EPIC-07 | SQLite state foundation with WAL/FULL/FK/busy timeout | - |
| P-062 | EPIC-07 | Stable external_id and source_id mapping | P-061 |
| P-063 | EPIC-07 | Idempotency keys and read-back before retry | P-062 |
| P-064 | EPIC-07 | Typed resource locks | - |
| P-065 | EPIC-07 | Saga and checkpoint persistence | - |
| P-066 | EPIC-07 | Desired-state reconciliation engine | P-063 |
| P-067 | EPIC-07 | Conflict resolution policy | - |
| P-068 | EPIC-07 | State migration framework | - |
| P-069 | EPIC-08 | Structured redacted JSON logging | P-050 |
| P-070 | EPIC-08 | Low-cardinality Prometheus metrics | P-069 |
| P-071 | EPIC-08 | Reporting projections and evidence bundles | P-069 |
| P-072 | EPIC-09 | Cloudflare MCP Server Portal exposure and deployment | P-026 |
| P-073 | EPIC-09 | Hermes notification and HITL integration | P-071 |
| P-074 | EPIC-10 | Mutation readiness gate and 0.2.0 roadmap | P-073 |

All dependency identifiers are zero-padded (`P-019`, `P-025`) and validated by `tests/test_release_contract.py`.
