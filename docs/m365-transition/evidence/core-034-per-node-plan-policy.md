# CORE-034 — Per-node BATCH/DAG/RUNBOOK policy

Status: **IMPLEMENTED_AWAITING_GATES_AND_PREDECESSOR_POST_MERGE**

## Objective

Ensure composite execution can never authorize a BATCH, DAG or RUNBOOK through one aggregate policy shortcut. Every semantic node must receive the same metadata-, security-tier- and scope-aware decision as an equivalent direct operation.

## Implementation

`m365_mcp.plan_policy` defines:

- closed plan kinds: `BATCH`, `DAG`, `RUNBOOK`;
- `PolicyNode` containing node id, semantic tool, optional typed scope, compatibility mutation override and dependency ids;
- `PolicyPlan` with structural validation;
- `NodePolicyResult` preserving the exact policy result for each node;
- `PlanPolicyResult` whose aggregate disposition is derived only after every node has been evaluated independently.

Aggregate precedence is fail closed:

```text
any DENY              -> plan DENY
else any REQUIRE_APPROVAL -> plan REQUIRE_APPROVAL
else                   -> plan ALLOW
```

Evaluation deliberately does not short-circuit on the first denial, so the caller receives a complete bounded per-node policy map rather than losing visibility into later nodes.

## Structural validation

Plans reject:

- empty node sets;
- duplicate node ids;
- self dependencies;
- duplicate dependency ids;
- references to unknown node ids;
- empty/untrimmed node ids and tool names.

CORE-034 validates dependency references but does not implement DAG scheduling or cycle detection; those remain execution-plane concerns in the later XAPP roadmap.

## Governance composition

Every node is passed independently to `MetadataPolicyEngine.evaluate()`. Therefore:

- an unknown tool denies only that node and makes the plan deny;
- a scope mismatch denies the affected node;
- a valid sibling does not inherit or transfer authorization;
- mutation disablement remains authoritative;
- an approval-required node promotes the plan to `REQUIRE_APPROVAL` but does not mark sibling reads as requiring approval;
- plan membership cannot lower CORE-032 security tier or bypass CORE-033 scope policy.

## Execution boundary

This module performs policy simulation only. It does not execute, schedule, retry or mutate any Microsoft 365 operation and does not introduce a public BATCH/DAG/RUNBOOK tool surface.

## Acceptance coverage

Tests cover independent node evaluation, unknown-tool denial, scope mismatch isolation, per-node approval retention, mutation-disablement preservation and invalid dependency structures.
