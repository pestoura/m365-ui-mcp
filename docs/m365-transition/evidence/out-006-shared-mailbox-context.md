# OUT-006 — Shared-mailbox scoped context model

Status: **IMPLEMENTED_ON_CURRENT_MAIN**

## Objective

Represent one reviewed shared-mailbox execution scope without carrying mailbox addresses, tenant/user identifiers, authenticated URLs or tenant content.

## Model

`m365_mcp.apps.outlook.shared_mailbox_context` introduces a closed shared-mailbox context state model:

```text
VERIFIED
PRIMARY_CONTEXT_INVALID
UNVERIFIED
AMBIGUOUS
PRIMARY_MAILBOX_CONTEXT
REATTESTATION_REQUIRED
```

A positive shared-mailbox context requires:

- a valid OUT-005 primary professional mailbox context;
- an observed reviewed shared-mailbox shell;
- an opaque SHA-256 scope digest;
- an opaque SHA-256 evidence digest.

The public projection exposes only bounded booleans/state and never the raw digests or mailbox identity.

## Fail-closed behavior

The model rejects or degrades:

- invalid primary professional context;
- ambiguous mailbox context;
- accidental primary-mailbox context;
- re-attestation-required state;
- observed shared shell without both scope/evidence digests;
- unobserved state carrying scope evidence;
- malformed digest shapes.

## Safety boundary

Outlook remains `RESERVED`. OUT-006 does not register public `outlook_*` tools, browser operations, selectors, URLs, live capability support or mutations. It stores no mailbox address, tenant/user identifier, cookie, token, auth header, storage state or Microsoft content. The Planner ABI is unchanged and no Microsoft Graph dependency is introduced.

## Acceptance coverage

Tests in `tests/test_outlook_shared_mailbox_context.py` prove verified/unverified/ambiguous/primary-indicator/re-attestation outcomes, digest-shape enforcement, scope-evidence coupling and the absence of identity-bearing public parameters.

## Integration base

Implemented directly on `main` after OUT-005 merged via PR #295; no stacked dependency remains.
