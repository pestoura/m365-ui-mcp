# CORE-035 — Approval plan digest

Status: **IMPLEMENTED_AWAITING_CURRENT_BASE_GATES**

## Objective

Create a canonical immutable digest that binds an approval to the exact policy-relevant shape of a multi-node mutating BATCH/DAG/RUNBOOK plan.

## Canonical digest

`m365_mcp.approval_digest` serializes a versioned `approval-plan-v1` payload with sorted JSON keys and compact separators, then computes lowercase SHA-256.

The digest binds:

- plan kind;
- node order;
- node id;
- semantic tool name and tool version;
- registry mutation class;
- CORE-032 security tier;
- effective mutation status;
- CORE-033 effective application/surface/account/container/mailbox/resource scope;
- dependency identities, canonicalized as a sorted set.

Changing any approval-relevant semantic attribute therefore produces a different digest. Reordering dependency ids alone does not, because dependency tuple presentation is not semantically meaningful.

## Fail-closed rules

Digest creation rejects:

- single-node plans;
- plans with no mutating node;
- unregistered tools;
- invalid or mismatched node scope;
- unsupported digest schema/algorithm representations.

The input `PolicyPlan` already rejects duplicate node ids and invalid dependency references through CORE-034.

## Security/privacy boundary

The canonical payload contains only reviewed semantic metadata. It deliberately excludes:

- Microsoft tenant content;
- raw resource identifiers;
- mailbox addresses;
- browser profile paths;
- cookies, tokens and storage state.

A digest is not an approval. CORE-036 owns persistent, single-use and replay-safe approval consumption. CORE-035 only establishes the immutable value to which that approval will be bound.

## Current integration gate

CORE-034 and PLN-MIG-001 are both merged and post-merge GREEN. This revision re-triggers the full mandatory PR suite against the current integrated `main`; previous branch GREEN evidence is not reused for merge.

## Acceptance coverage

Tests prove deterministic hashing, binding to node order/tool version/plan kind, canonical dependency ordering and fail-closed behavior for read-only, single-node, unknown-tool and invalid-scope plans.
