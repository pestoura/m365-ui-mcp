# CORE-042 — `INDETERMINATE` terminal state

Status: **INTEGRATED_ON_MAIN**

## Objective

Represent mutations whose resulting Microsoft state cannot be proven as an explicit terminal execution state instead of incorrectly treating them as `FAILED`, `COMPLETED`, or safe to retry.

## Lifecycle extension

CORE-042 extends the generalized CORE-040 lifecycle with:

```text
INDETERMINATE
```

It is a terminal state and may be entered only after execution has started:

```text
ACTIVE       -> INDETERMINATE
CHECKPOINTED -> INDETERMINATE
```

`PLANNED -> INDETERMINATE` is invalid because no external effect can yet have occurred.

## Required uncertainty evidence

An indeterminate checkpoint must carry a bounded semantic `uncertainty_code`, for example:

```text
READ_BACK_AMBIGUOUS
READ_BACK_NOT_PROVABLE
```

The code is metadata, not tenant content. Whitespace-bearing/free-form uncertainty text is rejected.

`INDETERMINATE` cannot carry a success `result_digest`; only `COMPLETED` may do so. Conversely, non-indeterminate states cannot carry an uncertainty code.

## Retry safety

CORE-038 already prevents blind retry when an external effect is unverified. CORE-042 provides the terminal lifecycle representation for the case where reconciliation/read-back cannot establish whether that effect occurred.

An `INDETERMINATE` checkpoint has no outgoing transition. Resuming or retrying therefore requires a new explicit governed recovery decision rather than mutating the existing lifecycle chain.

## Relationship to recovery metadata

CORE-041 declares whether a mutation has automatic, manual-only, or unavailable recovery metadata. That declaration does not convert an unprovable external state into a proven one. `INDETERMINATE` remains authoritative until separate evidence/recovery handling establishes a new governed operation.

## Security/privacy boundary

The terminal state carries only the semantic uncertainty code and the already-bounded checkpoint metadata. It does not store Microsoft response bodies, resource identifiers, mailbox identities, tenant content, browser/session secrets, cookies, tokens, or storage state.

## Acceptance coverage

Tests prove:

- `INDETERMINATE` is terminal;
- it cannot be entered before execution starts;
- a semantic uncertainty code is mandatory;
- other states cannot carry uncertainty metadata;
- success result digests are prohibited on indeterminate checkpoints;
- valid checkpoint chains can end in `INDETERMINATE` after ACTIVE/CHECKPOINTED.

## Current integration gate

CORE-041 is merged and post-merge GREEN on `main` at `5469821deab86505e51b19dfab3905ae35295eee`. PR #266 now targets that current integration base. This revision deliberately re-triggers the complete mandatory CI/security/image/Trivy/SBOM/documentation suite; stacked evidence is not reused for merge.

## Integration reconciliation

This requirement's delta is present in `main`. The mandatory CI gate set (compile/lint/type/contracts/tests, image build + Trivy + SBOM, filesystem/dependency/secret scanning) was GREEN on the merged pull request, and the full gate set was re-executed on post-merge `main` at `9b4a645`.

Mock mode only: no live Microsoft tenant was contacted, no capability is promoted to SUPPORTED by this record, Outlook stays RESERVED, and the 17-tool Planner public ABI is unchanged.
