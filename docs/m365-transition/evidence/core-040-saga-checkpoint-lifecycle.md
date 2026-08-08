# CORE-040 — Saga/checkpoint generalization

Status: **IMPLEMENTED_AWAITING_CURRENT_BASE_GATES**

## Objective

Introduce a cross-application, append-only execution checkpoint model that binds lifecycle state to the operation identities established by CORE-037, CORE-038 and CORE-039 without importing Planner-specific state into generic M365 core.

## Existing Planner boundary

The historical `planner_mcp.checkpoints` and `planner_mcp.sagas` packages currently contain documentation-only placeholders and no runtime implementation. CORE-040 leaves those packages untouched, avoiding an implicit behavior change in the preserved Planner surface.

## Generalized checkpoint binding

`m365_mcp.execution_lifecycle.ExecutionCheckpoint` binds one semantic node to:

- SHA-256 digest of an opaque saga/run identifier;
- monotonic checkpoint index;
- semantic node id;
- closed `ApplicationKey`;
- lifecycle state;
- CORE-038 idempotency key;
- CORE-039 typed lock keys in canonical acquisition order;
- optional CORE-037 state identity digest;
- result digest only at successful completion.

The underlying tenant request/result payload, Microsoft resource identifier, mailbox identity and browser/session data are not retained.

## Closed lifecycle

CORE-040 deliberately defines only:

```text
PLANNED
ACTIVE
CHECKPOINTED
COMPLETED
FAILED
```

Allowed transitions are explicit and fail closed. Terminal states cannot transition further. `CHECKPOINTED` may resume to `ACTIVE`, create another checkpoint, complete, or fail.

Two roadmap concepts are deliberately excluded:

- compensation availability/strategy is owned by CORE-041;
- `INDETERMINATE` is owned by CORE-042.

## Append-only chain invariants

`validate_checkpoint_chain()` requires:

- index zero starts at `PLANNED`;
- contiguous monotonic checkpoint indices;
- immutable saga/node/application binding;
- immutable CORE-038 idempotency key;
- immutable canonical lock set/order;
- immutable state-identity binding;
- only declared lifecycle transitions;
- no successors after a terminal checkpoint.

Each checkpoint exposes a deterministic SHA-256 `checkpoint_digest` over its bounded canonical metadata.

## Cross-application safety

A checkpoint rejects:

- a CORE-037 state identity whose application differs from the checkpoint application;
- an application/container/resource typed lock for another application.

Profile/account locks remain valid cross-application parents because their generic lock identity has no application field.

This permits one saga to contain separate Planner and Outlook node chains while preventing one node's state/locks from being silently rebound to another application.

## Security/privacy boundary

Opaque saga ids are immediately digested. The model does not persist raw saga ids, raw Microsoft resource ids, mailbox addresses, account emails, tenant content, browser profile paths, cookies, tokens or storage state.

## Acceptance coverage

Tests prove:

- checkpoint binding to generalized identity/idempotency/typed-lock metadata;
- monotonic legal lifecycle chains;
- terminal transition rejection;
- mandatory result digest at completion;
- cross-application state and lock mismatch rejection;
- immutable chain bindings;
- historical Planner checkpoint/saga placeholders remain unchanged.

## Current integration gate

CORE-039 is merged and post-merge GREEN on `main` at `2c1f4c59ac26c3d0819045c8f8a593aceb3eb90c`. PR #264 is now based directly on that integration point. Its CORE-040-specific Ruff spacing issue was corrected in advance; this revision deliberately re-triggers the complete mandatory current-base gate suite and does not reuse stacked evidence.
