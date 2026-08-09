# Power BI UI MCP — Delivery Operating Model

Status: **INCUBATION / VNEXT INPUT**

This document defines **how Power BI UI MCP work will be delivered once implementation is allowed to start**. It does not override the incubation gate `PBI-001`.

## Hard start gate

Implementation must not begin until the active Planner/Outlook M365 baseline is GREEN and versioned.

```text
PBI-001 PASS
      ↓
IMPLEMENTATION MAY START
```

Until then, only design, reconciliation, discovery planning, acceptance design and non-invasive documentation work may progress.

A gate that did not execute is not GREEN.

## Permanent progression rule

Once `PBI-001` permits implementation:

```text
GREEN | PASS | SUPPORTED | ACCEPTED
                 ↓
        CONTINUE AUTOMATICALLY
```

Stop only for a real blocker: authentication/MFA requiring the user, Conditional Access/device-compliance restriction, unsupported live Power BI surface, destructive ambiguity, security regression, shared M365 baseline regression, unavailable tenant/service, or insufficient evidence to support a capability claim.

## Delivery objective

Optimize for **time to a useful Power BI automation capability**, not for breadth of implemented UI mechanics.

Preferred progression:

```text
live read-only discovery
        ↓
workspace/report/page inventory
        ↓
semantic model + developer-surface discovery
        ↓
first safe read capability baseline
        ↓
first controlled reversible report mutation
        ↓
visual/page editing baseline
        ↓
DAX / M / TMDL fast paths
        ↓
reliable report-building workflows
        ↓
production-capable integration
```

Do not attempt to implement every Power BI feature before producing the first useful accepted baseline.

## Delivery topology

Normal execution uses:

```text
5–6 development lanes
+
1 Controller / Integration lane
```

Use fewer lanes when the UI or model dependencies are serial. Parallelism must reduce critical-path time, not create merge or browser-contract conflicts.

### Controller / Integration lane

The controller continuously:

1. reconciles `main`, Power BI incubation/implementation branches, PRs, CI and evidence;
2. identifies the next usable Power BI baseline;
3. identifies critical-path dependencies;
4. classifies failures;
5. fixes deterministic failures immediately where safe;
6. integrates GREEN lanes;
7. revalidates the M365 shared baseline;
8. launches the next independent wave;
9. prevents mock or code-only capabilities from being misreported as live support.

## Delivery waves

Power BI should be built in **vertical waves**.

### Example Wave A — live read discovery

```text
lane A: authentication/session readiness
lane B: workspace discovery
lane C: report/page discovery
lane D: UIContract/evidence harness
lane E: semantic model/developer-surface discovery
lane F: policy/capability projection
                 ↓
            integration
                 ↓
       READ-ONLY BASELINE
```

### Example Wave B — first controlled mutation

```text
lane A: page operation
lane B: visual target resolution
lane C: formatting/property contract
lane D: mutation/read-back verification
lane E: evidence/rollback
lane F: UI drift tests
                 ↓
            integration
                 ↓
      CONTROLLED MUTATION BASELINE
```

The actual wave must always be selected from current live repository and tenant evidence.

## Execution hierarchy

For every operation, prefer the highest-level reliable surface available:

```text
TMDL / model code surface
        >
DAX editor
        >
Power Query M / Advanced Editor
        >
semantic DOM / ARIA Playwright
        >
keyboard / clipboard acceleration
        >
geometry-aware canvas interaction
        >
vision-assisted recovery/validation
        >
absolute coordinates (last resort)
```

This hierarchy is also a delivery optimization: higher-level deterministic surfaces should be implemented before expensive brittle GUI choreography when they solve the same user intent.

## Vertical capability slice

A Power BI capability is most valuable when delivered end to end:

```text
semantic intent
   → policy/capability
   → target resolution
   → UIContract or developer surface
   → private worker execution
   → normalized result
   → evidence
```

For mutations:

```text
semantic intent
   → exact target
   → policy / approval if required
   → mutation
   → mandatory read-back
   → verified state
   → evidence / rollback or compensation
```

Avoid large horizontal foundations that cannot yet perform a useful accepted operation.

## Fast gates before expensive/live gates

Conceptual order:

```text
compile / lint / formatting
        ↓
type / schema / contract validation
        ↓
targeted mock/unit tests
        ↓
security / secret invariants
        ↓
worker/container validation
        ↓
controlled live read acceptance
        ↓
controlled live mutation acceptance
```

Do not consume a live authenticated browser session to discover failures that lint, typing or mock tests could have caught first.

## Failure classification

### Deterministic failure

Examples: lint, formatting, typing, schema, fixture, deterministic unit test.

```text
FAIL → inspect → patch → targeted retest → push → continue
```

No blind retries.

### Browser/UI failure

Classify explicitly:

```text
UI_DRIFT
AUTH_REQUIRED
MFA_REQUIRED
SESSION_EXPIRED
CONDITIONAL_ACCESS_BLOCKED
CAPABILITY_ABSENT
TARGET_AMBIGUOUS
INDETERMINATE
POWERBI_SERVICE_FAILURE
```

Do not silently fall back to arbitrary clicks or coordinates when semantic state is not proven.

### Shared M365 blocker

Freeze Power BI promotion if it would regress Planner, Outlook, shared policy, worker isolation, protocol contracts or the current versioned M365 baseline.

## Definition of Delivery

Implementation is not delivery.

A read capability is delivered only when:

```text
SEMANTIC CONTRACT
+ TESTS
+ POLICY
+ UI/DEVELOPER-SURFACE ATTESTATION
+ CONTROLLED LIVE ACCEPTANCE
+ SANITIZED EVIDENCE
= DELIVERED READ
```

A mutation additionally requires:

```text
EXACT TARGET RESOLUTION
+ IDEMPOTENCY/RETRY BEHAVIOR
+ READ-BACK
+ FINAL-STATE VERIFICATION
+ ROLLBACK/COMPENSATION WHERE FEASIBLE
= DELIVERED MUTATION
```

Use explicit capability states such as:

```text
PLANNED
SPECIFIED_ONLY
IMPLEMENTED_MOCK_ONLY
IMPLEMENTED_NOT_ATTESTED
SUPPORTED_LIVE
DEGRADED
BLOCKED
```

## Product-specific first baselines

### Baseline PBI-A — authenticated read discovery

Using the controlled existing report target, prove session readiness and semantic discovery of workspace, report and page without mutation.

### Baseline PBI-B — report structure read

Read and normalize useful report/page/visual/model metadata through semantic or developer surfaces.

### Baseline PBI-C — first controlled reversible mutation

Perform one bounded report edit in controlled scope, prove the exact target, read back the result and restore/compensate where feasible.

### Baseline PBI-D — report-building workflow

Prove a small end-to-end workflow such as page/visual creation or model edit using the highest-level available execution path and complete evidence.

Each baseline should be independently versionable and demonstrable.

## CI / integration rules

- Prefer PR validation for feature branches and full validation on the integration/main baseline; avoid equivalent duplicate CI work.
- Fast gates precede expensive browser/container/live acceptance gates.
- Security and acceptance requirements are never removed for speed.
- Integrate by waves when several independent lanes compose one baseline.
- Merge automatically when required gates executed and are GREEN and no real blocker exists.
- Revalidate the shared M365 baseline after Power BI integration changes.

## Worker isolation rule

Power BI remains isolated from Planner and Outlook at process/container, profile, state, evidence and logging boundaries. Delivery pressure must never justify sharing browser credential/session state across application workers.

## WIP and critical path

The Controller lane continuously asks:

```text
What is the shortest safe path to the next demonstrable Power BI capability?
```

Finish/integrate current waves before opening unlimited future backlog work. Parallel work is useful only when it does not starve live acceptance and integration.

## Conversation / agent restart rule

Any new execution session must first reconcile:

```text
current m365 main
+ versioned Planner/Outlook baseline
+ PBI-001
+ Power BI branch/PR state
+ CI
+ tenant/live evidence
```

Then continue the highest-priority safe wave. Conversation memory is not a gate.

## Permanent execution algorithm

```text
CHECK PBI-001
   ↓ PASS
RECONCILE LIVE STATE
   ↓
IDENTIFY NEXT DEMONSTRABLE BASELINE
   ↓
FORM DELIVERY WAVE
   ↓
PARALLEL IMPLEMENTATION
   ↓
FAST GATES
   ↓
FAIL? ── yes ──→ FIX / RETEST
   │
   no
   ↓
INTEGRATE
   ↓
CONTROLLED LIVE ACCEPTANCE
   ↓
BASELINE GREEN
   ↓
VERSION + EVIDENCE
   ↓
NEXT WAVE
```

This operating model remains active for the Power BI program unless explicitly superseded by a documented design decision.