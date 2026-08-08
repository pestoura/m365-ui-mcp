# Governance

## Decision model

Every operation resolves to exactly one policy decision:

| Decision | Meaning |
| --- | --- |
| `ALLOW` | Execute now, record telemetry. |
| `DENY` | Refuse. Typed error, no side effect, no retry. |
| `REQUIRE_APPROVAL` | Suspend; emit an approval request; execute only after a valid, unused, unexpired approval bound to this operation fingerprint. |

**Default-deny**: if no rule matches and the tool's `mutation_class` is `GOVERNED_WRITE` or
`DESTRUCTIVE`, the decision is `DENY`.

## Mutation classes

| Class | Definition | Default decision | Reversible |
| --- | --- | --- | --- |
| `READ` | No tenant state change. | ALLOW | n/a |
| `SAFE_WRITE` | Additive, low blast radius, trivially reversible (e.g. add a task to a bucket). | ALLOW under rule | yes |
| `GOVERNED_WRITE` | Changes project semantics: schedule, dependencies, assignments, custom fields, sprint membership. | REQUIRE_APPROVAL | usually |
| `DESTRUCTIVE` | Deletes or irreversibly restructures: delete plan/task/bucket, bulk reassign, portfolio restructure, import overwrite. | REQUIRE_APPROVAL + explicit rule | no |

## Approval object

```json
{
  "approval_id": "apr_…",
  "operation_fingerprint": "sha256:…",
  "operation_id": "op_…",
  "mutation_class": "GOVERNED_WRITE",
  "requested_by": "subject-id",
  "granted_by": "subject-id",
  "granted_at": "RFC3339",
  "expires_at": "RFC3339",
  "state": "PENDING|GRANTED|CONSUMED|EXPIRED|REVOKED",
  "single_use": true
}
```

Rules: persisted; `CONSUMED` is terminal; fingerprint covers tool name, contract version,
normalized arguments and target `external_id` set — any change invalidates the approval;
approvals are never inferred from a previous run.

## Trust levels

Declared per tool in the ExtendedToolManifest:

| `trust_level` | Meaning |
| --- | --- |
| `INTROSPECTION` | Describes the system itself; no tenant contact. |
| `TENANT_READ` | Reads tenant data through the browser. |
| `TENANT_WRITE` | Mutates tenant data. |
| `PRIVILEGED` | Affects governance, policy or portfolio-scope structures. |

## Attestation governance

A capability's `support_level` may only advance with recorded evidence
(see [ui-contract.md](ui-contract.md) and
[planner-premium-capabilities.md](planner-premium-capabilities.md)). Advancing a capability to
`SUPPORTED` requires: attested selectors, a successful read, a successful read-back for mutating
capabilities, and a linked evidence handle. Documentation-only changes MUST NOT advance a state.

## Roles

| Role | Responsibility |
| --- | --- |
| Maintainer | Architecture, ADRs, policy rules, release gates. |
| Operator | Performs interactive auth and MFA approval in Authenticator; grants approvals. |
| Reviewer | Enforces DoD and security controls on PRs. |

The MCP client (ChatGPT) is never an approver of MFA and never a policy authority.

## Change control

- Architectural or security-boundary changes require an ADR.
- Weakening any `SEC-*` control requires an ADR plus explicit maintainer sign-off in the PR.
- Contract-breaking changes bump the minor version pre-1.0 and update
  [traceability.md](traceability.md).

## Escalation / blockers

Typed blockers stop work rather than degrade safety:
`BLOCKER_CONDITIONAL_ACCESS`, `BLOCKER_UI_DRIFT`, `BLOCKER_POLICY_UNCERTAIN`,
`BLOCKER_AMBIGUOUS_SESSION`, `BLOCKER_LICENSE_UNVERIFIED`, `BLOCKER_EVIDENCE_MISSING`.
Each is reported with `operation_id` and the remediation owner.
