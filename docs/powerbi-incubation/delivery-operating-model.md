# Power BI UI MCP — Delivery Operating Model

Status: **INCUBATION / VNEXT INPUT**

This document defines **how Power BI UI MCP work will be delivered once implementation is allowed to start**. It does not override the incubation gate `PBI-001`.

The model follows JDS-001 principles: next usable baseline, critical path, vertical slices, bounded WIP, fast feedback, evidence-based support and explicit recovery/rollback behavior where applicable.

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

Stop only for a real blocker: authentication/MFA requiring the user, Conditional Access/device-compliance restriction, unsupported live Power BI surface, destructive ambiguity, security regression, shared M365 baseline regression, unavailable tenant/service, or insufficient evidence for a capability claim.

## Delivery objective

Optimize for **time to a useful Power BI automation capability**, not breadth of implemented UI mechanics.

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

Do not implement every Power BI feature before producing the first accepted useful baseline.

## Work topology and WIP

Power BI implementation does **not** require a fixed number of development lanes or agents.

Parallel work is used only where it materially reduces critical-path time. For the current Jarvas/Hermes development environment, use this as an upper bound rather than a target:

```text
active development WIP <= 5–6 lanes
```

Use fewer lanes when UI/model dependencies are serial or when additional work would create merge, browser-contract or CI pressure.

A lane may be executed by a human, agent, automation or other implementation mechanism.

### Integration Controller role

For concurrent work, one role owns integration throughput. It may be human or automated.

It continuously:

1. reconciles current M365 baseline, Power BI branch/PRs, CI and evidence;
2. identifies the next demonstrable Power BI capability and critical path;
3. keeps WIP bounded;
4. classifies failures;
5. repairs/routes deterministic failures;
6. integrates GREEN work;
7. revalidates the shared M365 baseline;
8. opens the next independent work only when capacity exists;
9. prevents mock/code-only capabilities from being reported as live support.

## Delivery waves and vertical slices

Waves are optional coordination devices for independent slices that compose one baseline. They are not a mandatory architecture or staffing model.

A Power BI capability should be delivered end to end:

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

The first implementation should be a walking skeleton: authenticate/establish session readiness, discover one controlled workspace/report/page path, return a normalized read and retain sanitized evidence before broad feature work begins.

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

Higher-level deterministic surfaces should be implemented before brittle GUI choreography when they solve the same semantic intent.

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

Do not consume a live authenticated browser session to discover failures that deterministic local gates could catch first.

## Failure classification

### Deterministic failure

```text
FAIL → inspect → root cause → patch → targeted retest → continue
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

A live read requires:

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

Use explicit capability states:

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

### PBI-A — authenticated read discovery

Using a controlled existing report target, prove session readiness and semantic discovery of workspace, report and page without mutation.

### PBI-B — report structure read

Read and normalize useful report/page/visual/model metadata through semantic or developer surfaces.

### PBI-C — first controlled reversible mutation

Perform one bounded report edit in controlled scope, prove exact target, read back the result and restore/compensate where feasible.

### PBI-D — report-building workflow

Prove a small end-to-end workflow such as page/visual creation or model edit using the highest-level available execution path and complete evidence.

Each baseline should be independently demonstrable and versionable.

## CI / integration rules

- Prefer short-lived branches and PR validation.
- Avoid equivalent duplicate CI work when repository protections permit.
- Fast gates precede expensive browser/container/live acceptance gates.
- Security and acceptance requirements are never removed for speed.
- Use merge-queue or equivalent serialized integration validation when concurrent GREEN PRs can invalidate one another.
- Merge automatically only when required gates actually executed and are GREEN.
- Revalidate the shared M365 baseline after Power BI integration changes.

## Worker isolation rule

Power BI remains isolated from Planner and Outlook at process/container, profile, state, evidence and logging boundaries. Delivery pressure never justifies sharing browser credential/session state across application workers.

## Resume rule

Any resumed execution session first reconciles:

```text
current m365 main
+ versioned Planner/Outlook baseline
+ PBI-001
+ Power BI branch/PR state
+ CI
+ tenant/live evidence
```

Conversation memory is not a gate.

## Permanent algorithm

```text
CHECK PBI-001
   ↓ PASS
RECONCILE LIVE STATE
   ↓
IDENTIFY NEXT DEMONSTRABLE BASELINE
   ↓
SELECT MINIMUM USEFUL WORK SET
   ↓
BOUNDED PARALLEL IMPLEMENTATION
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
NEXT BASELINE
```

This operating model remains active for the Power BI program unless explicitly superseded by a documented design decision.