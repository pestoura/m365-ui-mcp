# OUT-006 — Shared-mailbox scoped context model

Status: **PREIMPLEMENTED_STACKED_AWAITING_OUT_005**

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

Outlook remains `RESERVED`. OUT-006 does not register public `outlook_*` tools, browser operations, selectors, URLs, live capability support or mutations. It stores no mailbox address, tenant/user identifier, cookie, token, auth header, storage state or Microsoft content.

## Dependency gate

This PR is stacked on OUT-005 and must not merge until OUT-005 is merged and post-merge `main` is GREEN. It will then be retargeted to `main` and revalidated through the complete mandatory CI/security/image/Trivy/SBOM/documentation suite.
