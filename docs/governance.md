# Governance

This document is the policy and decision authority for the Planner MCP. It defines how every
operation resolves to exactly one decision, the mutation classes that drive that decision, the
single-use approval object that gates governed and destructive writes, the trust levels declared per
tool, the attestation gate that prevents capability claims without evidence, the roles and their
separation of duties, and the change-control and blocker discipline that keeps the system safe to
operate. It is referenced by [security.md](security.md) (SEC-050..SEC-056, SEC-060..SEC-067),
[reconciliation.md](reconciliation.md), [state-model.md](state-model.md),
[planner-premium-capabilities.md](planner-premium-capabilities.md) and requirement R-38 in
[traceability.md](traceability.md).

## Decision model

Every operation resolves to exactly one policy decision:

| Decision | Meaning |
| --- | --- |
| `ALLOW` | Execute now, record telemetry. |
| `DENY` | Refuse. Typed error, no side effect, no retry. |
| `REQUIRE_APPROVAL` | Suspend; emit an approval request; execute only after a valid, unused, unexpired approval bound to this operation fingerprint. |

**Default-deny**: if no rule matches and the tool's `mutation_class` is `GOVERNED_WRITE` or
`DESTRUCTIVE`, the decision is `DENY`.

### Policy evaluation algorithm

The policy engine runs the following deterministic procedure for every tool invocation before any
tenant contact:

```text
evaluate(tool, args, capability_state, auth_state, blockers):
  if auth_state.state != AUTHENTICATED and tool.trust_level in {TENANT_READ, TENANT_WRITE}:
      return DENY, code=AUTH_REQUIRED            # SEC-063
  if any capability in scope not at least READ_ATTESTED (read) / MUTATION_ATTESTED (write):
      return DENY, code=UNATTESTED_CAPABILITY    # SEC-051
  if any blocker active for scope:
      return DENY, code=blocker_code              # SEC-043, terminal
  if policy_rules failed to load:
      return DENY, code=POLICY_UNCERTAIN          # SEC-064 (only health allowed)
  rule = match_rule(tool, args)                  # most-specific match wins
  if rule is None:
      if tool.mutation_class in {GOVERNED_WRITE, DESTRUCTIVE}:
          return DENY, code=NO_MATCHING_RULE      # default-deny
      return ALLOW                                # READ / SAFE_WRITE under no rule
  if rule.decision == DENY: return DENY, rule.code
  if rule.decision == REQUIRE_APPROVAL:
      apr = find_valid_approval(tool.fingerprint)
      if apr is None: return REQUIRE_APPROVAL, code=APPROVAL_REQUIRED
      return ALLOW, bound_approval=apr            # consumed atomically at apply
  return ALLOW
```

The decision, its inputs, and the matched rule id are written to the audit trail (SEC-056) so any
refusal is explainable after the fact. The algorithm is pure: identical inputs always yield the
identical decision; there is no hidden state, no sampling, no fallback to a weaker rule.

## Mutation classes

| Class | Definition | Default decision | Reversible |
| --- | --- | --- | --- |
| `READ` | No tenant state change. | ALLOW | n/a |
| `SAFE_WRITE` | Additive, low blast radius, trivially reversible (e.g. add a task to a bucket). | ALLOW under rule | yes |
| `GOVERNED_WRITE` | Changes project semantics: schedule, dependencies, assignments, custom fields, sprint membership. | REQUIRE_APPROVAL | usually |
| `DESTRUCTIVE` | Deletes or irreversibly restructures: delete plan/task/bucket, bulk reassign, portfolio restructure, import overwrite. | REQUIRE_APPROVAL + explicit rule | no |

A `mutation_class` is declared immutably in the ExtendedToolManifest and may only be *raised* by an
ADR, never lowered by a runtime rule (SEC-052: policy may raise a requirement, never lower it). The
class drives the default decision row above and the read-back/compensation expectations in
[reconciliation.md](reconciliation.md).

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

### Approval lifecycle and replay defence

The approval object is the single control that converts `REQUIRE_APPROVAL` into a permitted apply.
Its lifecycle and hardening:

1. **Issue** — on `REQUIRE_APPROVAL`, the engine emits an approval request carrying the
   `operation_fingerprint` (sha256 over tool name, contract version, ui_contract_version,
   canonical args, sorted target `external_id`s — idempotency.md §Operation fingerprint). State =
   `PENDING`.
2. **Grant** — an Operator grants it (`GRANTED`). Granting records `granted_by`, `granted_at`, and
   an `expires_at` (default 15 minutes).
3. **Bind** — the approval is bound to exactly one `operation_fingerprint`. A different fingerprint
   (different args, scope, or contract version) does not match and yields a fresh
   `APPROVAL_REQUIRED` (no "approve then swap", SEC-054).
4. **Consume** — at apply time, consumption is atomic: state flips `GRANTED → CONSUMED` inside the
   same transaction as the first checkpoint write. A second apply with the same fingerprint finds
   `CONSUMED` and is rejected (`OPERATION_IN_FLIGHT` / replay defence, SEC-055).
5. **Expire** — past `expires_at` the approval is `EXPIRED` and unusable; the operation must be
   re-planned and re-approved.
6. **Revoke** — an Operator may `REVOKE` a `PENDING`/`GRANTED` approval; a revoked approval can
   never be consumed.

There is no standing approval, no wildcard scope, and no approval that survives a restart of the
target plan's state (SEC-055). Approvals are never granted by the MCP client (ChatGPT) or by Hermes;
they are an Operator action only (see §Roles).

## Trust levels

Declared per tool in the ExtendedToolManifest:

| `trust_level` | Meaning |
| --- | --- |
| `INTROSPECTION` | Describes the system itself; no tenant contact. |
| `TENANT_READ` | Reads tenant data through the browser. |
| `TENANT_WRITE` | Mutates tenant data. |
| `PRIVILEGED` | Affects governance, policy or portfolio-scope structures. |

Trust level is orthogonal to mutation class: a `PRIVILEGED` tool (e.g. one that changes policy or
portfolio scope) is also evaluated against `GOVERNED_WRITE`/`DESTRUCTIVE` rules and additionally
requires an audit event tagged `PRIVILEGED`. `INTROSPECTION` tools are the only ones reachable when
the policy engine itself cannot load (SEC-064 allows only `planner_health` through).

## Attestation governance

A capability's `support_level` may only advance with recorded evidence
(see [ui-contract.md](ui-contract.md) and
[planner-premium-capabilities.md](planner-premium-capabilities.md)). Advancing a capability to
`SUPPORTED` requires: attested selectors, a successful read, a successful read-back for mutating
capabilities, and a linked evidence handle. Documentation-only changes MUST NOT advance a state.

The attestation gate is enforced at two points:
- **Capability gate** — a tool whose capability is below `READ_ATTESTED` (reads) or
  `MUTATION_ATTESTED` (writes) is `DENY`ed regardless of policy rules (SEC-051). This is what makes
  "no evidence ⇒ no support" a runtime property, not just a documentation rule.
- **Matrix update gate** — a PR that advances a capability row in
  [planner-premium-capabilities.md](planner-premium-capabilities.md) without an evidence handle in
  the attestation log is rejected by review and by the G10 traceability gate.

## Roles

| Role | Responsibility |
| --- | --- |
| Maintainer | Architecture, ADRs, policy rules, release gates. |
| Operator | Performs interactive auth and MFA approval in Authenticator; grants approvals. |
| Reviewer | Enforces DoD and security controls on PRs. |

The MCP client (ChatGPT) is never an approver of MFA and never a policy authority.

### Separation of duties

- The **Operator** performs human-only acts: signing in (SEC-020, the password is typed by a human
  into Microsoft's page), approving MFA number matching in Authenticator (SEC-032), and granting
  operation approvals. The Operator never writes policy or merges releases.
- The **Maintainer** writes policy, ADRs, and release gates but cannot grant an approval for an
  operation they authored (self-approval is prohibited; the grantor must differ from the requester).
- The **Reviewer** enforces the Definition of Done and the SEC-* controls on every PR; the Reviewer
  may be the Maintainer only when a second sign-off is recorded for security-boundary changes.
- **ChatGPT** (the MCP client) is a caller only. It receives tool results and sanitized errors; it
  cannot invoke auth, cannot grant approvals, and cannot influence the policy decision (SEC-013,
  Z0 trust zone).
- **Hermes** is strictly one-way for operational events (SEC-013, ZH): it receives sanitized
  notifications and can perform human-in-the-loop approval of *its own* blocked operations, but it
  cannot mutate Planner, cannot grant policy approvals, and cannot influence the auth state machine
  (see [hermes-integration.md](hermes-integration.md) §3–§4, R-16/R-17).

## Change control

- Architectural or security-boundary changes require an ADR.
- Weakening any `SEC-*` control requires an ADR plus explicit maintainer sign-off in the PR.
- Contract-breaking changes bump the minor version pre-1.0 and update
  [traceability.md](traceability.md).

Additional change-control rules:
- Every PR references a backlog key and updates traceability (R-38, G10 gate). A PR that changes a
  requirement, adds an ADR, adds a tool, or changes a test mapping must update the traceability
  table in the same PR.
- A `mutation_class` raise, a `trust_level` raise to `PRIVILEGED`, or a new `DESTRUCTIVE` tool
  requires an ADR and a Reviewer sign-off.
- Removing or lowering a security control (`SEC-*`) is never a silent diff; it is an ADR plus a
  maintainer note in the PR body explaining the accepted risk and its owner.
- Versioning: `< 1.0` uses `0.MINOR.PATCH`; a contract-breaking change (UIContract fragment shape,
  tool argument schema, approval schema) bumps `MINOR` and is reflected in `planner_readiness`
  `contract_version`.

## Escalation / blockers

Typed blockers stop work rather than degrade safety:
`BLOCKER_CONDITIONAL_ACCESS`, `BLOCKER_UI_DRIFT`, `BLOCKER_POLICY_UNCERTAIN`,
`BLOCKER_AMBIGUOUS_SESSION`, `BLOCKER_LICENSE_UNVERIFIED`, `BLOCKER_EVIDENCE_MISSING`.
Each is reported with `operation_id` and the remediation owner.

### Blocker taxonomy and remediation owners

| Blocker | Trigger | Terminal? | Remediation owner |
| --- | --- | --- | --- |
| `BLOCKER_CONDITIONAL_ACCESS` | CA policy demands compliant/managed device (SEC-041) | yes (for capability) | Organisation / device owner |
| `BLOCKER_UI_DRIFT` | live contract ≠ attested fragment (SEC-060) | yes until re-attest | Maintainer (re-attest) |
| `BLOCKER_POLICY_UNCERTAIN` | policy rules failed to load (SEC-064) | yes until reload | Maintainer / on-call |
| `BLOCKER_AMBIGUOUS_SESSION` | session identity ambiguous (e.g. multiple profiles) | yes for attempt | Operator (re-auth) |
| `BLOCKER_LICENSE_UNVERIFIED` | required license not observed | yes (mark `UNSUPPORTED_TENANT`) | Tenant admin |
| `BLOCKER_EVIDENCE_MISSING` | capability invoked without attestation | yes for attempt | Maintainer (attest) |

A blocker is reported with `operation_id`, the triggering `evidence_hash`/`contract_version` where
relevant, and the remediation owner, and raises an operator alert (R-40). Blockers are never retried
(SEC-043); resolution is an out-of-band, human decision.

### Audit trail requirements

Every decision (ALLOW/DENY/REQUIRE_APPROVAL), every approval issue/grant/consume/expire/revoke, and
every blocker firing is appended to the hash-chained audit trail (R-13, observability.md §6) with:
`operation_id`, `tool_name`, `fingerprint`, `decision`/`event`, the matched `rule_id` or `code`,
`subject` (requester/grantor), and `ts` (RFC3339). The trail is append-only; the chain is verified on
export so tampering is detectable.

## Worked example

A caller invokes `planner_task_assign` (mutation_class `GOVERNED_WRITE`, trust `TENANT_WRITE`) to
assign person X to task T.

1. `auth_state.state == AUTHENTICATED` → passes auth gate.
2. Task-assignment capability is `MUTATION_ATTESTED` → passes capability gate.
3. No blocker active → passes blocker gate.
4. Policy rule matches `GOVERNED_WRITE` → decision `REQUIRE_APPROVAL`, code `APPROVAL_REQUIRED`.
5. A valid, unexpired, fingerprint-matching approval exists (granted by Operator, not the caller) →
   `ALLOW` with bound approval.
6. At apply, the approval is consumed atomically with the first checkpoint; any replay with the
   same fingerprint is rejected as `CONSUMED`.
7. If no approval existed, the operation was suspended and the caller told to obtain one — no tenant
   contact occurred.

## Requirement mapping

| Topic | Requirement / control |
| --- | --- |
| Default-deny, single decision | SEC-050, SEC-064 |
| Capability gate before allow | SEC-051 |
| Governed/destructive always require approval | SEC-052 |
| Non-replayable single-use approval | SEC-053, SEC-054, SEC-055 |
| Fail closed on ambiguity/drift | SEC-060..SEC-067 |
| PR references backlog + traceability | R-38, G10 |
| Hermes one-way, no mutation | R-16, R-17, SEC-013 |
| Audit trail append-only | R-13 |
