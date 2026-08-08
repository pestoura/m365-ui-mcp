# Acceptance

Acceptance defines what evidence must exist before Planner MCP behaviour, capability states and
releases may be claimed as valid.

Companions: [`testing.md`](testing.md), [`release-process.md`](release-process.md),
[`ui-contract.md`](ui-contract.md), [`deployment.md`](deployment.md),
[`planner-premium-capabilities.md`](planner-premium-capabilities.md) and
[`definition-of-done.md`](definition-of-done.md).

## 1. Acceptance principle

Planner capability acceptance is **browser/UI-evidenced**. Microsoft Graph documentation or
availability is never a substitute for the Planner Premium UI evidence required by this product.

Mock evidence proves implementation logic and fail-closed behavior. It does not prove that the real
tenant currently exposes the same UI/capability.

## 2. Acceptance levels

| Level | Environment | Data | Mutations | Automation | Purpose |
| --- | --- | --- | --- | --- | --- |
| A0 Structural | CI/static | none | none | automated | docs/contracts/security structure |
| A1 Functional | unit/contract/mock | synthetic | mock only where required | automated | component logic |
| A2 Isolated | full local stack + mock UI | synthetic | mock only | automated | end-to-end release safety |
| A3 Live read-only | real tenant | real/request scoped | none | manual | live capability/UI read evidence |
| A4 Live mutation | dedicated non-production Planner test plan | disposable | controlled | manual only | later live write support |

For `0.1.0`, A4 is out of scope and no public mutation tool is registered.

## 3. Capability-state evidence

The canonical capability states are:

```text
UNVERIFIED_LIVE
DISCOVERED
READ_ATTESTED
MUTATION_ATTESTED
SUPPORTED
DEGRADED
UI_DRIFT
BLOCKED_CONDITIONAL_ACCESS
```

Minimum interpretation:

| State | Evidence meaning |
| --- | --- |
| `UNVERIFIED_LIVE` | specified/implemented without sufficient real-tenant evidence |
| `DISCOVERED` | capability observed in the target tenant/UI |
| `READ_ATTESTED` | read path and UIContract fragment verified with live evidence |
| `MUTATION_ATTESTED` | later: governed write + fresh UI read-back verified in an authorized test plan |
| `SUPPORTED` | all capability-specific product/security/UI/evidence/release gates satisfied |
| `DEGRADED` | bounded capability exists but an expected condition/dependency is degraded |
| `UI_DRIFT` | UIContract no longer matches; affected capability fails closed |
| `BLOCKED_CONDITIONAL_ACCESS` | tenant policy requires an unsupported/unacceptable device condition |

No state is promoted merely because Microsoft documentation says the feature exists.

## 4. A0/A1 acceptance

Structural/functional acceptance covers:

- compile/lint/type/schema/contract gates;
- exact tool/manifest metadata;
- policy and error taxonomy;
- auth-state/MFA/CA/enrolment behavior;
- UIContract registry and fail-closed drift behavior;
- redaction/cardinality/privacy tests;
- read-model normalization/snapshot logic;
- mock-only mutation framework safety where P-031 infrastructure exists;
- documentation and traceability integrity.

For 0.1.0, contract acceptance explicitly proves exactly 17 public `READ` tools and no public
mutation/generic browser primitive.

## 5. A2 isolated acceptance — IA-01..IA-16

A2 runs the full local stack against the mock Planner UI with no live Planner credentials or tenant
network path.

Canonical scenario families:

| IA | Scenario | Required result |
| --- | --- | --- |
| IA-01 | control-plane health/readiness and contract bootstrap | healthy/schema-valid |
| IA-02 | private worker reachability boundary | reachable only from intended internal path |
| IA-03 | plan/task read model | deterministic normalized reads |
| IA-04 | project snapshot | stable hash for unchanged synthetic state |
| IA-05 | UIContract drift fixture | `UI_DRIFT`, fail closed, no arbitrary action |
| IA-06 | authentication required/session-expired fixture | correct formal state/blocker |
| IA-07 | Conditional Access managed-device fixture | `BLOCKER_CONDITIONAL_ACCESS`, zero bypass/retry |
| IA-08 | Intune/enrolment/device-registration fixture | blocker/refusal; no enrolment action |
| IA-09 | missing/invalid policy | `DENY` |
| IA-10 | approval expiry/replay/change | reject stale/replayed/mismatched approval |
| IA-11 | idempotency duplicate/conflict | one bounded effect in mock; conflict handled |
| IA-12 | timeout/unknown mutation outcome in mock | fresh read-back before retry; uncertainty explicit |
| IA-13 | saga/checkpoint recovery | verified steps not blindly replayed |
| IA-14 | telemetry/redaction/cardinality | zero prohibited leakage/findings |
| IA-15 | container/network/mount hardening | all posture assertions pass |
| IA-16 | supply-chain/release evidence structure | scans/SBOM/evidence schemas valid |

A later implementation may split scenarios further, but IA-01..IA-16 remain the canonical release
acceptance family owned by P-069.

## 6. A2 execution procedure

Preconditions:

- exact candidate SHA checked out;
- required earlier CI gates green;
- no live Planner credentials in the environment;
- isolated/mock navigation configuration active;
- production image digest requirements either resolved for a release candidate or explicitly
  recorded as a blocker for a non-release development run.

Procedure:

1. start a fresh isolated stack;
2. verify health/readiness and network boundaries;
3. seed the synthetic mock Planner state;
4. run UIContract/mock semantic validation;
5. execute IA-01..IA-16;
6. collect sanitized results/log/audit/metrics evidence;
7. verify no live Planner target was contacted;
8. validate evidence hashes/schema;
9. tear down disposable state and verify no unexpected residue.

A2 may exercise internal mutation/reconciliation framework behavior against the mock UI. It never
enables those handlers in the public 0.1.0 MCP registry.

## 7. Evidence bundle

A release/acceptance evidence bundle is immutable and bound to the exact git SHA/environment.
Representative structure:

```text
evidence/<level>/<timestamp>-<git-sha>/
  manifest.json
  environment.json
  summary.json
  scenarios/
  ui-contract/
  security/
  sbom/
```

The manifest includes as applicable:

- acceptance level;
- git SHA/product/contract/UIContract versions;
- scenario outcomes;
- environment mode;
- container image digests;
- SBOM references/digests;
- scan result references;
- evidence file hashes;
- blocker codes;
- operator identifier for manual A3/A4 without unnecessary personal data.

Do not place passwords/tokens/cookies/browser profile exports or unredacted tenant content into an
evidence bundle.

## 8. Read-back evidence

For later mutation acceptance, success requires a **fresh UI read** after the action.

Read-back evidence records:

- operation/resource type and bounded reference;
- requested normalized state/hash;
- observed normalized state/hash;
- intended changed fields;
- guard fields that must remain unchanged where defined;
- verdict (`VERIFIED`, mismatch/partial, `UNKNOWN_OUTCOME`);
- attempt/deadline metadata;
- UIContract/contract version used.

The write response itself is not read-back evidence. A timeout is not authorization to retry.

## 9. A3 live read-only acceptance

A3 is manual, operator-controlled and mutation-free.

Required controls:

- use only the dedicated professional Chromium profile;
- ensure public registry/mode is read-only;
- no mutation handler/tool registered;
- authenticate interactively in the browser;
- MFA approval only in Microsoft Authenticator;
- stop on managed/compliant/enrolled/certificate Conditional Access requirement;
- stop on device-enrolment/Company Portal/Identity Broker/MDM prompts;
- perform only planned read/navigation observations;
- attest only UIContract fragments/capabilities actually observed;
- sanitize evidence before persistence/distribution.

Post-session evidence includes:

- exact build/contract/UIContract versions;
- capabilities/fragments observed;
- read results/evidence hashes required by the acceptance protocol;
- confirmation that no mutation operation occurred;
- explicit blocker records for anything not verifiable.

An A3 session never auto-promotes unrelated capabilities.

## 10. A4 live mutation acceptance — later only

A4 is introduced only after the relevant mutation release exists and A3/read safety is established.
It is never automated and never uses a production project.

Requirements include:

- dedicated disposable/non-production Planner test plan;
- explicit scope and human oversight;
- valid UIContract/live capability evidence;
- policy/approval/idempotency/locks enabled;
- dry-run reviewed before governed/destructive operations;
- fresh read-back after each mutation;
- exact partial/unknown outcome handling;
- documented safe compensation where applicable;
- immediate stop on first unexplained divergence.

Only A4 evidence can contribute to `MUTATION_ATTESTED`/write `SUPPORTED` state.

## 11. Acceptance rejection conditions

Acceptance fails when any applicable condition occurs:

- documentation gate has error/warning;
- required CI/security gate did not run or failed;
- secret/redaction finding;
- public 0.1 registry contains a mutation tool;
- live tenant was contacted by automated CI mutation testing;
- UIContract miss/drift on a capability being claimed;
- unexpected mutation during A3;
- Conditional Access/enrolment boundary was bypassed;
- read-back mismatch/unknown outcome was hidden as success;
- worker is reachable outside the intended private boundary;
- required image digest is not real/verified;
- HIGH/CRITICAL Trivy policy fails;
- required SBOM invalid or empty;
- evidence hash/schema does not verify.

## 12. Release relationship

For `0.1.0`:

- A2/IA-01..IA-16 is required;
- A3 is required only for claims of live Planner read support;
- if A3 is not complete, release documentation explicitly avoids such claims;
- A4 is not part of the release;
- P-071/P-072/P-073 evidence must close before P-074.

A gate unavailable because of GitHub billing/platform/quota is `BLOCKED/UNAVAILABLE`, never PASS.

## 13. Backlog mapping

| Acceptance concern | Canonical P-key(s) |
| --- | --- |
| Complete CI | P-068 |
| IA-01..IA-16 isolated acceptance | P-069 |
| Live read-only procedure | P-070 |
| Traceability closure | P-071 |
| Documentation completeness | P-072 |
| Release process/gates | P-073 |
| 0.1.0 release | P-074 |
| Mutation framework safety used by mock scenarios | P-031 |
| UI/auth prerequisites | P-014..P-024 |

Acceptance evidence does not redefine the backlog; it proves it.
