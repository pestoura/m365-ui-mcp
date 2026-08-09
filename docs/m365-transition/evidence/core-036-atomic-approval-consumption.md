# CORE-036 — Atomic approval consumption

Status: **INTEGRATED_ON_MAIN**

## Objective

Persist approvals for CORE-035 approval-plan digests and guarantee that one approval can authorize at most one successful consumption, including under concurrent consumers and process/store reopen.

## Implementation

`m365_mcp.approval_store.ApprovalStore` uses a dedicated SQLite database and stores only the approval handle plus bounded CORE-035 digest metadata and lifecycle timestamps.

Each approval is bound to:

- digest schema version;
- digest algorithm;
- exact digest value;
- digest node count;
- opaque approval handle;
- creation time;
- optional expiry time;
- one consumption timestamp.

Consumption executes inside `BEGIN IMMEDIATE`, re-checks the complete digest binding while holding the write transaction and performs a conditional `UPDATE ... consumed_at IS NULL` before commit.

## Closed consumption outcomes

- `CONSUMED` — the matching approval was atomically spent;
- `NOT_FOUND` — no approval exists for the opaque handle;
- `DIGEST_MISMATCH` — the handle exists but is not bound to the supplied plan digest;
- `ALREADY_CONSUMED` — replay or concurrent loser after the approval was spent;
- `EXPIRED` — the optional expiry boundary has passed.

Any non-`CONSUMED` result is fail-closed and cannot authorize execution.

## Persistence and replay guarantees

The approval lifecycle is persisted independently of the Python process. Tests reopen the store before consumption and prove the record remains authoritative.

A concurrency test uses two independent `ApprovalStore` instances against the same SQLite database and attempts to consume the same approval concurrently. Exactly one consumer may return `CONSUMED`; the other must observe `ALREADY_CONSUMED`.

A digest mismatch does not spend the approval, so an accidental or malicious attempt against a different plan cannot destroy the legitimate approval while also never authorizing that different plan.

## Security/privacy boundary

The approval database does not store:

- Microsoft tenant content;
- mailbox addresses;
- raw Microsoft resource identifiers;
- browser profile paths;
- cookies, tokens or storage state.

The generated approval handle is opaque and URL-safe. No public MCP approval tool or UI is introduced in this phase.

## Current integration gate

CORE-035 is merged and post-merge GREEN on `main`, together with the completed Planner schema and Tool Registry migrations. PR #258 is now based directly on that integrated `main`. This revision deliberately re-triggers the complete mandatory suite; stacked-branch evidence is not reused for merge.

## Integration reconciliation

This requirement's delta is present in `main`. The mandatory CI gate set (compile/lint/type/contracts/tests, image build + Trivy + SBOM, filesystem/dependency/secret scanning) was GREEN on the merged pull request, and the full gate set was re-executed on post-merge `main` at `9b4a645`.

Mock mode only: no live Microsoft tenant was contacted, no capability is promoted to SUPPORTED by this record, Outlook stays RESERVED, and the 17-tool Planner public ABI is unchanged.
