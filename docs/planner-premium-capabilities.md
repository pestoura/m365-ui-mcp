# Planner Premium capabilities

The capability model is built from real evidence: tenant/license availability, UI observed,
UIContract status, read attestation, mutation attestation.
**Microsoft Graph API availability is not a column and never determines support level.**

Support levels: `unsupported`, `planned`, `read_unattested`, `read_attested`, `mutation_attested`.

## Capability matrix

| capability | tenant/license availability | UI observed | UIContract status | read attestation | mutation attestation | support level | evidence/notes |
| --- | --- | --- | --- | --- | --- | --- | --- |
| plans.read | unknown_no_evidence | not_observed | UNVERIFIED_LIVE | unattested | not_implemented_0_1_0 | read_unattested | Mock-mode only; live attestation pending P-050 |
| tasks.read | unknown_no_evidence | not_observed | UNVERIFIED_LIVE | unattested | not_implemented_0_1_0 | read_unattested | Mock-mode only |
| buckets.read | unknown_no_evidence | not_observed | UNVERIFIED_LIVE | unattested | not_implemented_0_1_0 | read_unattested | Domain skeleton present |
| dependencies.read | unknown_no_evidence | not_observed | UNVERIFIED_LIVE | unattested | not_implemented_0_1_0 | read_unattested | Premium-only surface |
| scheduling.read | unknown_no_evidence | not_observed | UNVERIFIED_LIVE | unattested | not_implemented_0_1_0 | read_unattested | Premium-only surface |
| goals.read | unknown_no_evidence | not_observed | UNVERIFIED_LIVE | unattested | not_implemented_0_1_0 | read_unattested | Premium-only surface |
| sprints.read | unknown_no_evidence | not_observed | UNVERIFIED_LIVE | unattested | not_implemented_0_1_0 | read_unattested | Premium-only surface |
| resources.read | unknown_no_evidence | not_observed | UNVERIFIED_LIVE | unattested | not_implemented_0_1_0 | read_unattested | Premium-only surface |
| custom_fields.read | unknown_no_evidence | not_observed | UNVERIFIED_LIVE | unattested | not_implemented_0_1_0 | read_unattested | Premium-only surface |
| portfolios.read | unknown_no_evidence | not_observed | UNVERIFIED_LIVE | unattested | not_implemented_0_1_0 | read_unattested | Premium-only surface |
| project_snapshot.read | unknown_no_evidence | not_observed | UNVERIFIED_LIVE | unattested | not_implemented_0_1_0 | read_unattested | Composite read over plan + tasks |
| any.mutation | n/a | n/a | UNVERIFIED_LIVE | n/a | not_implemented_0_1_0 | unsupported | Policy denies all mutations in 0.1.0 |

`planner_capabilities()` recomputes this matrix at runtime from live evidence rather than from this
static document.
