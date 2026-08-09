# OUT-005 — Primary-mailbox context verification

Status: **INTEGRATED_CLEAN_ON_MAIN**

## Objective

Establish a fail-closed, content-free assertion that the active Outlook context represents the professional account's primary mailbox before any future primary-mailbox capability can be promoted.

## Composition

OUT-005 builds on CORE-024 rather than inventing a second account-identity mechanism.

The verifier consumes:

- the existing sanitized `AccountContext` assertion;
- a bounded Outlook primary-shell observation;
- an optional re-attestation requirement.

It does not consume or persist mailbox addresses, tenant identifiers, user identifiers, authenticated URLs, cookies, tokens or storage state.

## Closed mailbox states

- `VERIFIED`
- `ACCOUNT_CONTEXT_INVALID`
- `UNVERIFIED`
- `AMBIGUOUS`
- `SHARED_MAILBOX_CONTEXT`
- `REATTESTATION_REQUIRED`

A primary-mailbox context is valid only when:

```text
CORE-024 account_context.valid
AND primary Outlook shell observed
AND evidence digest present
AND no shared-mailbox indicator
AND no ambiguity
AND no re-attestation requirement
```

Every other state fails closed.

## Evidence boundary

A positive shell observation requires a lowercase SHA-256 evidence digest. The model retains only that digest and bounded booleans; it does not carry the underlying tenant content or mailbox identity.

A shared-mailbox indicator is explicitly rejected as primary-mailbox context. Shared mailbox scope is intentionally deferred to `OUT-006`.

## Support boundary

This phase verifies only the semantic context model. It does not:

- register an `outlook_*` public tool;
- add an Outlook capability to the effective Capability Registry;
- add a worker browser operation;
- claim live support;
- mutate Microsoft 365 state.

Outlook therefore remains `RESERVED`.

## Acceptance coverage

Tests prove:

- invalid professional account context fails closed;
- verified account plus primary-shell evidence can produce `VERIFIED`;
- shared and ambiguous mailbox contexts are rejected;
- stale/re-attestation-required context is rejected;
- unobserved primary mailbox remains `UNVERIFIED`;
- observed state requires a valid SHA-256 evidence digest;
- public verifier inputs and observation fields contain no mailbox/user/tenant identity parameters.

## Dependency gate

OUT-004 is merged and integrated on current `main`, so this dependency is satisfied. The work is integrated on `main` and revalidated against the current integration base with the mandatory CI/security/image/Trivy/SBOM/documentation gates.

## Integration reconciliation

The delta is integrated in `main` (clean branch rebased on GREEN `main` and merged through PR #295). Mandatory CI gates (compile/lint/type/contracts/tests, image build + Trivy + SBOM, filesystem/dependency/secret scanning) were GREEN on the merged PR and the post-merge `main` gate set was re-executed locally at `12b363c`.

This records mock-mode integration only. No live Microsoft tenant was contacted, no Outlook capability is promoted to SUPPORTED, the Outlook application stays RESERVED with no public `outlook_*` MCP tool, and the Planner public tool ABI is unchanged.
